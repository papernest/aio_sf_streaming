"""
aio_sf_streaming
~~~~~~~~~~~~~~~~

aio_sf_streaming is a simple asyncio Salesforce Streaming API client for
Python 3.6+
"""
import asyncio
import aiohttp
from .core import BaseSalesforceStreaming
from .connectors import (
    BaseConnector,
    PasswordSalesforceStreaming,
    RefreshTokenSalesforceStreaming,
)
from .mixins import (
    TimeoutAdviceMixin,
    AutoVersionMixin,
    ReplayMixin,
    ReplayType,
    AutoReconnectMixin,
    ReSubscribeMixin,
    AllMixin,
)
from .__version__ import __version__


class SimpleSalesforceStreaming(AllMixin, PasswordSalesforceStreaming):  # Password flow
    """
    A simple helper class providing all-in-one functionalities.

    :param username: User login name
    :param password: User password
    :param client_id: OAuth2 client Id
    :param client_secret: Oauth2 client secret
    :param sandbox: If ``True``, the connexion will be made on a sandbox,
        from ``https://test.salesforce.com`` instead of the main login
        route at ``https://login.salesforce.com``.
    :param version: The API version to use. For example ``'42.0'``.
    :param loop: Asyncio loop used
    :param connector: ``aiohttp`` connector used for main session. Mainly used
        for test purpose.
    :param login_connector: ``aiohttp`` connector used during connection. Mainly
        used for test purpose.
    :param retry_sub_duration: Duration between subscribe retry if server is
        too buzy.
    :param retry_factor: Factor amplification between each successive retry
    :param retry_max_duration: Maximum value of the retry duration
    :param retry_max_count: Maximum count of retry, after this count is reach,
        response or exception are propagated.

    **Usage example**::

        class MyClient(SimpleSalesforceStreaming):
            def __init__(self):
                self.replays = []
                super().__init__(username='my-username',
                                 password='my-password',
                                 client_id='my-client-id',
                                 client_secret='my-client-secret')

            async def store_replay_id(self, channel, replay_id, creation_time):
                # We only store replay id without any use
                self.replays.append((channel, replay_id, creation_time))

            async def get_last_replay_id(self, channel):
                # We ask for only use new events
                return EventType.NEW_EVENTS

        async def print_events():
            async with MyClient() as client:
                await client.subscribe('/topic/Foo')
                async for message in client.events():
                    channel = message['channel']
                    print(f"Message received on {channel} : {message}")

        loop = asyncio.get_event_loop()
        loop.run_until_complete(print_event())

    """

    def __init__(
        self,
        username: str,
        password: str,
        client_id: str,
        client_secret: str,
        *,
        sandbox: bool = False,
        version: str = "42.0",
        loop: asyncio.AbstractEventLoop = None,
        connector: aiohttp.BaseConnector = None,
        login_connector: aiohttp.BaseConnector = None,
        retry_sub_duration: float = 0.1,
        retry_factor: float = 1.,
        retry_max_duration: float = 30.,
        retry_max_count: int = 20,
    ) -> None:
        super().__init__(
            username=username,
            password=password,
            client_id=client_id,
            client_secret=client_secret,
            sandbox=sandbox,
            version=version,
            loop=loop,
            connector=connector,
            login_connector=login_connector,
            retry_sub_duration=retry_sub_duration,
            retry_factor=retry_factor,
            retry_max_duration=retry_max_duration,
            retry_max_count=retry_max_count,
        )


class SimpleRefreshTokenSalesforceStreaming(
    AllMixin, RefreshTokenSalesforceStreaming
):  # Refresh token flow
    """
    A simple helper class providing all-in-one functionalities.

    :param refresh_token: Refresh token
    :param client_id: OAuth2 client Id
    :param client_secret: Oauth2 client secret
    :param sandbox: If ``True``, the connexion will be made on a sandbox,
        from ``https://test.salesforce.com`` instead of the main login
        route at ``https://login.salesforce.com``.
    :param version: The API version to use. For example ``'42.0'``.
    :param loop: Asyncio loop used
    :param connector: ``aiohttp`` connector used for main session. Mainly used
        for test purpose.
    :param login_connector: ``aiohttp`` connector used during connection. Mainly
        used for test purpose.
    :param retry_sub_duration: Duration between subscribe retry if server is
        too buzy.
    :param retry_factor: Factor amplification between each successive retry
    :param retry_max_duration: Maximum value of the retry duration
    :param retry_max_count: Maximum count of retry, after this count is reach,
        response or exception are propagated.

    **Usage example**::

        class MyClient(SimpleRefreshTokenSalesforceStreaming):
            def __init__(self):
                self.replays = []
                super().__init__(refresh_token='refresh_token',
                                 client_id='my-client-id',
                                 client_secret='my-client-secret')

            async def store_replay_id(self, channel, replay_id, creation_time):
                # We only store replay id without any use
                self.replays.append((channel, replay_id, creation_time))

            async def get_last_replay_id(self, channel):
                # We ask for only use new events
                return EventType.NEW_EVENTS

        async def print_events():
            async with MyClient() as client:
                await client.subscribe('/topic/Foo')
                async for message in client.events():
                    channel = message['channel']
                    print(f"Message received on {channel} : {message}")

        loop = asyncio.get_event_loop()
        loop.run_until_complete(print_event())

    """

    def __init__(
        self,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        *,
        sandbox: bool = False,
        version: str = "42.0",
        loop: asyncio.AbstractEventLoop = None,
        connector: aiohttp.BaseConnector = None,
        login_connector: aiohttp.BaseConnector = None,
        retry_sub_duration: float = 0.1,
        retry_factor: float = 1.,
        retry_max_duration: float = 30.,
        retry_max_count: int = 20,
    ) -> None:
        super().__init__(
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            sandbox=sandbox,
            version=version,
            loop=loop,
            connector=connector,
            login_connector=login_connector,
            retry_sub_duration=retry_sub_duration,
            retry_factor=retry_factor,
            retry_max_duration=retry_max_duration,
            retry_max_count=retry_max_count,
        )
