"""
Core module: define the root base class with main logic
"""
import abc
import asyncio
import copy
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import aiohttp

logger = logging.getLogger("aio_sf_streaming")

# Typing utils
JSONObject = Dict[str, Any]
JSONList = List[JSONObject]
JSONType = Union[JSONObject, JSONList]


class BaseSalesforceStreaming(abc.ABC):
    """
    Base low-level *aio-sf-streaming* class.

    Can not be used directly: must be sub-classed with at least one connector
    implementation. The class provide basic functionalities. Additional
    functionalities can be added with provided mixins.

    The main logic is implemented here but you should not use it directly.

    :param sandbox: If ``True``, the connexion will be made on a sandbox,
        from ``https://test.salesforce.com`` instead of the main login
        route at ``https://login.salesforce.com``.
    :param version: The API version to use. For example ``'42.0'``.
    :param loop: Asyncio loop used
    :param connector: ``aiohttp`` connector used for main session. Mainly used
        for test purpose.

    This class supports the context manager protocol for self closing.

    All main members are coroutine, even if default implementation does do any
    asynchronous call. With this convention, sub classes and mixins can easily
    override this members and do complex call.

    See :py:class:`SimpleSalesforceStreaming` for an usage example.
    """

    version: str  #: SF api version to use
    sandbox: bool  #: Use test server
    connector: aiohttp.BaseConnector  #: aiohttp connector for main session
    instance_url: Optional[str]  #: Instance url (retrieved with token)
    session: Optional[aiohttp.ClientSession]  #: Underlying connection
    client_id: Optional[str]  #: The client id token from handshake
    message_count: int  #: Message id count
    timeout: int  #: Timeout connection duration
    should_stop: bool  #: Set to True to stop streaming

    #: Header used in all requests
    base_header: dict = {"Accept": "application/json"}

    def __init__(
        self,
        *,
        sandbox: bool = False,
        version: str = "42.0",
        loop: asyncio.AbstractEventLoop = None,
        connector: aiohttp.BaseConnector = None,
    ) -> None:
        self.version = version
        self.sandbox = sandbox
        self._loop = loop
        self.connector = connector
        self.instance_url = None
        self.session = None
        self.client_id = None
        self.message_count = 0
        self.timeout = 120
        self.should_stop = False
        super().__init__()

    # -------------------- High level api --------------------

    async def start(self) -> None:
        """
        Connect to Salesforce, authenticate and init CometD connexion.

        A best practice is to use async context manager interface that will
        call this method directly.
        """
        self.session = await self.create_connected_session()
        await self.handshake()

    async def subscribe(self, channel: str) -> JSONList:
        """
        Subscribe to a channel. Can be used directly::

            await client.subscribe('/topic/Foo')

        This method, and the underlying protocol, are safe to be started as
        an background task::

            loop.create_task(client.subscribe('/topic/Foo'))

        """
        response = await self.send(await self.get_subscribe_payload(channel))
        logger.info("Subscribe response: %r", response)
        return response

    async def messages(self) -> JSONObject:
        """
        Asynchronous generator that fetch new messages and return one as soon
        as one is available::

            async for message in client.messages():
                channel = message['channel']
                print(channel, ':', message)

        This method iterate over **all** messages, even on internal/meta one.
        If you want to only iterate over messages from channels you subscribed,
        you should use :py:func:`BaseSalesforceStreaming.events`.

        .. warning::
            Linked to the underlying protocol, long-pooling based, the client
            should reconnect as soon as possible. Practically, client have 40
            seconds to reconnect. If your processing take a longer time, a new
            connection should be made. You should avoid doing long processing
            between each iteration or launch this processing into a background
            task.

        """
        while True:
            if self.should_stop:
                return
            try:
                response = await self.send(
                    {"channel": "/meta/connect", "connectionType": "long-polling"}
                )
            except asyncio.TimeoutError:
                logger.info("Timeout")
                continue
            except aiohttp.ClientResponseError as error:
                if error.code == 408:
                    # Timeout
                    logger.info("Timeout")
                    continue
                else:
                    raise

            if self.should_stop:
                return

            logger.info("Messages: received %r", response)
            for message in response:
                if self.should_stop:
                    return
                yield message

    async def events(self) -> JSONObject:
        """
        Asynchronous generator that fetch new events and return one as soon
        as one is available::

            async for message in client.events():
                channel = message['channel']
                print(channel, ':', message)

        This method is different from :py:func:`BaseSalesforceStreaming.messages`
        because it filter messages and provide only those related to the
        channels you subscribed.
        """
        async for message in self.messages():
            if not message.get("channel", "").startswith("/meta/"):
                yield message

    async def ask_stop(self) -> None:
        """
        Ask client to stop receiving event::

            async for event in client.events():
                ...
                if ...:
                    await client.ask_stop()

        This call will eventually stop
        :py:func:`BaseSalesforceStreaming.messages` and
        :py:func:`BaseSalesforceStreaming.events` async generator but this can
        take some time if not called inside the loop body: the generator will
        wait a timeout response from Salesforce server.
        """
        self.should_stop = True

    async def unsubscribe(self, channel: str) -> JSONList:
        """
        Unsubscribe to a channel. Can be used directly::

            await client.unsubscribe('/topic/Foo')

        This method, and the underlying protocol, are safe to be started as
        an background task::

            loop.create_task(client.unsubscribe('/topic/Foo'))

        """
        response = await self.send(await self.get_unsubscribe_payload(channel))
        logger.info("Unsubscribe response: %r", response)
        return response

    async def stop(self) -> None:
        """
        Disconnect to Salesforce and close underlying connection.

        A best practice is to use async context manager interface that will
        call this method directly.
        """
        await self.ask_stop()
        await self.disconnect()
        await self.close_session()

    # -------------------- Connection logic --------------------

    @property
    def token_url(self) -> str:
        """
        The url that should be used to fetch an access token.
        """
        url_prefix = "test" if self.sandbox else "login"
        return f"https://{url_prefix}.salesforce.com/services/oauth2/token"

    @abc.abstractmethod
    async def fetch_token(self) -> Tuple[str, str]:
        """
        Abstract coroutine method of connector that must provide an access
        token and the instance url linked.
        """

    async def create_connected_session(self) -> aiohttp.ClientSession:
        """
        This coroutine create an ``aiohttp.ClientSession`` using fetched token
        """
        token, self.instance_url = await self.fetch_token()

        base_header = copy.deepcopy(self.base_header)
        base_header.update({"Authorization": f"Bearer {token}"})

        session = aiohttp.ClientSession(
            connector=self.connector, headers=base_header, loop=self.loop
        )
        return session

    async def close_session(self) -> None:
        """
        Close the underlying ``aiohttp.ClientSession`` connection
        """
        if self.session is None:
            return
        await self.session.close()
        self.session = None

    # -------------------- Bayeux/CometD logic layer --------------------

    @property
    def end_point(self) -> str:
        """
        Cometd endpoint
        """
        return f"/cometd/{self.version}/"

    async def get_handshake_payload(self) -> JSONObject:
        """
        Provide the handshake payload
        """
        return {
            "channel": "/meta/handshake",
            "supportedConnectionTypes": ["long-polling"],
            "version": "1.0",
            "minimumVersion": "1.0",
        }

    async def get_subscribe_payload(self, channel: str) -> JSONObject:
        """
        Provide the subscription payload for a specific channel
        """
        return {"channel": "/meta/subscribe", "subscription": channel}

    async def get_unsubscribe_payload(self, channel: str) -> JSONObject:
        """
        Provide the unsubscription payload for a specific channel
        """
        return {"channel": "/meta/unsubscribe", "subscription": channel}

    async def send(self, data: JSONObject) -> JSONType:
        """
        Send data to CometD server when the connection is established::

            # Manually disconnect
            await client.send({'channel': '/meta/disconnect'})

        """
        self.message_count += 1

        # Add  id and client_id to payload
        data = copy.copy(data)
        data["id"] = str(self.message_count)
        if self.client_id:
            data["clientId"] = self.client_id

        # Post data
        return await self.post(self.end_point, json=data)

    async def handshake(self) -> JSONList:
        """
        Coroutine that perform an handshake (mandatory before any other action)
        """
        self.message_count = 0

        response = await self.send(await self.get_handshake_payload())
        logger.info("Handshake response: %r", response)
        self.client_id = response[0]["clientId"]

        return response

    async def disconnect(self) -> JSONList:
        """
        Disconnect from the SF streaming server
        """
        return await self.send({"channel": "/meta/disconnect"})

    # -------------------- IO layer helpers --------------------

    async def get(self, sub_url: str, **kwargs) -> JSONType:
        """
        Perform a simple json get request from an internal url::

            response = await.client.get('/myendpoint/')

        """
        return await self.request("get", sub_url, **kwargs)

    async def post(self, sub_url: str, **kwargs) -> JSONType:
        """
        Perform a simple json post request from an internal url::

            response = await.client.post('/myendpoint/', json={'data': 'foo'})

        """
        return await self.request("post", sub_url, **kwargs)

    async def request(self, method: str, sub_url: str, **kwargs) -> JSONType:
        """
        Perform a simple json request from an internal url
        """
        url = f"{self.instance_url}{sub_url}"
        logger.info("Perform %r to %r with %r", method, url, kwargs)

        async with self.session.request(
            method, url, timeout=self.timeout, **kwargs
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()

        return data

    # -------------------- SPECIALS METHODS -------------------- #

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """
        Running event loop
        """
        if self._loop is None:
            self._loop = asyncio.get_event_loop()
        return self._loop

    # Asynchronous context manager

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.stop()
