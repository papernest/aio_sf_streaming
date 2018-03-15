"""
Core module: define the root base class with main logic
"""
import abc
import asyncio
import copy
import logging

import aiohttp

logger = logging.getLogger('aio_sf_streaming')


class BaseSalesforceStreaming(abc.ABC):
    """
    Base SalesforceStreaming class. Can not be used directly: must be
    sub-classed with at least one connector implementation. The class provide
    basic functionalities. Additional functionalities can be added with
    provided mixins.
    """
    base_header = {'Accept': 'application/json'}

    def __init__(self, *,
                 sandbox=False,
                 version='42.0',
                 loop=None,
                 connector=None):
        """
        Manage the main streaming functionalities.

        Keywords options:

        :param sandbox: If ``True``, the connexion will be made on a sandbox,
            from ``https://test.salesforce.com`` instead of the main login
            route at ``https://login.salesforce.com``.
        :param version: The API version to use. For example ``'42.0'``.
        :param loop: Asyncio loop used
        :param connector: aiohttp connector used for main session. Mainly used
        for test purpose.
        """
        self.version = version          # SF api version to use
        self.sandbox = sandbox          # Use test server
        self._loop = loop               # Asyncio event_loop
        self.connector = connector      # aiohttp connector for mail session
        self.instance_url = None        # Instance url (retrieved with token)
        self.session = None             # Underlying connection
        self.client_id = None           # The client id token from handshake
        self.message_count = None       # Message id count
        self.timeout = 120              # Timeout connection duration
        self.should_stop = False        # Set to True to stop streaming

    # -------------------- High level api --------------------

    async def start(self):
        """
        Helper method doing all starting call
        """
        self.session = await self.create_connected_session()
        await self.handshake()

    async def subscribe(self, channel):
        """
        Subscribe to a channel
        """
        response = await self.send(await self.get_subscribe_payload(channel))
        logger.info("Subscribe response: %r", response)
        return response

    async def messages(self):
        """
        Fetch new messages and return one as soon as one is available.
        """
        while True:
            if self.should_stop:
                return
            try:
                response = await self.send({
                    'channel': '/meta/connect',
                    'connectionType': 'long-polling'})
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

    async def events(self):
        """
        Fetch new events and return one as soon as one is available.

        All "meta" events linked to protocol are dropped.
        """
        async for message in self.messages():
            if not message.get('channel', '').startswith('/meta/'):
                yield message

    async def unsubscribe(self, channel):
        """
        Unsubscribe from a channel
        """
        response = await self.send(await self.get_unsubscribe_payload(channel))
        logger.info("Unsubscribe response: %r", response)
        return response

    async def stop(self):
        """
        Helper method doing all stopping call
        """
        await self.ask_stop()
        await self.disconnect()
        await self.close_session()

    # -------------------- Connection logic --------------------

    @property
    def token_url(self):
        """
        Provide the token url
        """
        url_prefix = 'test' if self.sandbox else 'login'
        return f'https://{url_prefix}.salesforce.com/services/oauth2/token'

    @abc.abstractmethod
    async def fetch_token(self):
        """
        Abstract method of connector that must provide an access token and the
        instance url linked.
        """

    async def create_connected_session(self):
        """
        This coroutine create an aiohttp ClientSession using fetched token
        """
        token, self.instance_url = await self.fetch_token()

        base_header = copy.deepcopy(self.base_header)
        base_header.update({'Authorization': f"Bearer {token}"})

        session = aiohttp.ClientSession(
            connector=self.connector, headers=base_header, loop=self.loop)
        return session

    async def close_session(self):
        """
        Close the underlying connection
        """
        if self.session is None:
            return
        await self.session.close()
        self.session = None

    # -------------------- Bayeux/CometD logic layer --------------------

    @property
    def end_point(self):
        """
        Provide cometd endpoint
        """
        return f'/cometd/{self.version}/'

    async def get_handshake_payload(self):
        """
        Provide the handshake payload
        """
        return {
            'channel': '/meta/handshake',
            'supportedConnectionTypes': ['long-polling'],
            'version': '1.0',
            'minimumVersion': '1.0'
        }

    async def get_subscribe_payload(self, channel):
        """
        Provide the subscription payload for a specific channel
        """
        return {'channel': '/meta/subscribe',
                'subscription': channel}

    async def get_unsubscribe_payload(self, channel):
        """
        Provide the unsubscription payload for a specific channel
        """
        return {'channel': '/meta/unsubscribe',
                'subscription': channel}

    async def handshake(self):
        """
        Coroutine that perform an handshake (mandatory before any other action)
        """
        self.message_count = 0

        response = await self.send(await self.get_handshake_payload())
        logger.info("Handshake response: %r", response)
        self.client_id = response[0]['clientId']

        return response

    async def ask_stop(self):
        """
        Ask client to stop receiving event. Cant take some time.
        """
        self.should_stop = True

    async def disconnect(self):
        """
        Disconnect from the SF streaming server
        """
        return await self.send({'channel': '/meta/disconnect'})

    # -------------------- IO layer helpers --------------------

    async def send(self, data):
        """
        Send data to CometD server when the connection is established
        """
        self.message_count += 1

        # Add  id and client_id to payload
        data = copy.copy(data)
        data['id'] = str(self.message_count)
        if self.client_id:
            data['clientId'] = self.client_id

        # Post data
        return await self.post(self.end_point, json=data)

    async def get(self, sub_url, **kwargs):
        """
        Perform a simple json get request from an internal url
        """
        return await self.request('get', sub_url, **kwargs)

    async def post(self, sub_url, **kwargs):
        """
        Perform a simple json post request from an internal url
        """
        return await self.request('post', sub_url, **kwargs)

    async def request(self, method, sub_url, **kwargs):
        """
        Perform a simple json request from an internal url
        """
        url = f'{self.instance_url}{sub_url}'
        logger.info("Perform %r to %r with %r", method, url, kwargs)

        async with self.session.request(method, url, timeout=self.timeout,
                                        **kwargs) as resp:
            resp.raise_for_status()
            data = await resp.json()

        return data

    # -------------------- SPECIALS METHODS -------------------- #

    @property
    def loop(self):
        """
        Provide running event loop
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
