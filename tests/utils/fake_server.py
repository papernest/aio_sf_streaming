"""
Fake sf server

We create a fake resolver and servers allowing to simulate SF logic for our
tests.
Heavily inspired from:
 - <https://github.com/aio-libs/aiohttp/blob/master/examples/fake_server.py>
 - <https://gist.github.com/ambivalentno/e311ea008d05938ac5dd3048ce76e3d1>
"""
import datetime
import asyncio
from collections import deque, defaultdict
import pathlib
import ssl
import socket
from aiohttp import web
from aiohttp.resolver import DefaultResolver
from aiohttp.test_utils import unused_port


class FakeResolver:
    """
    Fake resolver will redirect provider host to a specific local port
    """
    _LOCAL_HOST = {0: '127.0.0.1',
                   socket.AF_INET: '127.0.0.1',
                   socket.AF_INET6: '::1'}

    def __init__(self, fakes, *, loop):
        """fakes -- dns -> port dict"""
        self._fakes = fakes
        self._resolver = DefaultResolver(loop=loop)

    async def resolve(self, host, port=0, family=socket.AF_INET):
        """
        Resolve an host: check if a fake server is registred and redirect to it.
        If the host is unknown, raise an error
        """
        fake_port = self._fakes.get(host)
        if fake_port is not None:
            return [{'hostname': host,
                     'host': self._LOCAL_HOST[family], 'port': fake_port,
                     'family': family, 'proto': 0,
                     'flags': socket.AI_NUMERICHOST}]
        raise OSError("DNS lookup failed")


class BaseFakeServer:
    """
    Base class for fake SF server
    """
    def __init__(self, *, loop):
        self.loop = loop
        self.app = web.Application(loop=loop)
        self.handler = None
        self.server = None
        self.port = None
        self.host = None
        # Use fake certificate for https
        here = pathlib.Path(__file__)
        ssl_cert = here.parent / 'server.crt'
        ssl_key = here.parent / 'server.key'
        self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.ssl_context.load_cert_chain(str(ssl_cert), str(ssl_key))

    @property
    def host_mapping(self):
        """
        provide host <-> port mapping for this server
        """
        return {self.host: self.port}

    async def start(self):
        """
        Start web server
        """
        self.port = unused_port()
        self.handler = self.app.make_handler()
        self.server = await self.loop.create_server(self.handler,
                                                    '127.0.0.1', self.port,
                                                    ssl=self.ssl_context)

    async def stop(self):
        """
        Stop web server
        """
        self.server.close()
        await self.server.wait_closed()
        await self.app.shutdown()
        await self.handler.shutdown()
        await self.app.cleanup()


class FakeLoginSfServer(BaseFakeServer):
    """
    Fake SF login server
    """

    def __init__(self, *, loop):
        super().__init__(loop=loop)
        self.host = 'login.salesforce.com'
        self.app.router.add_routes(
            [web.post('/services/oauth2/token', self.retrieve_token)])

    async def retrieve_token(self, _):
        """
        This route always return the same auth token
        """
        return web.json_response({
            'token_type': 'Bearer',
            'instance_url': 'https://foo.salesforce.com',
            'access_token': 'my-token'})


class FakeSfServer(BaseFakeServer):
    """
    Fake cometd SF server: only support one user !!!
    """

    def __init__(self, *, loop):
        super().__init__(loop=loop)
        self.host = 'foo.salesforce.com'
        self.app.router.add_routes(
            [web.get('/services/data/', self.version_history),
             web.post('/cometd/42.0/', self.cometd)])

        self.client_id = None               # Store the current client id
        self.received_messages = []         # Store all received messages
        self.subscribed_channels = set()    # Store subscribed channels
        self._events_id = defaultdict(int)  # Store event id for each channel
        self._futures = deque()             # Future queue used to push result

    def push_result(self, channel, message):
        """
        Push result to connected client
        """
        # We do not push event to not-subscribed channels
        if channel not in self.subscribed_channels:
            return
        # Update event count
        self._events_id[channel] += 1
        event_id = self._events_id[channel]
        # Create a fake date based on pushed message count
        created_date = datetime.datetime(
            2018, 3, 15, 13, 42, sum(self._events_id.values())).isoformat()
        # Create message
        event = {
            "data": {
                "sobject": message,
                "event": {
                    "replayId": event_id,
                    "createdDate": created_date
                }
            },
            "channel": channel
        }
        self.push_event(event)

    def push_event(self, event):
        """
        Push a raw event to connected client
        """
        # Do not add a future if there is already one waiting for result
        if len(self._futures) != 1 or self._futures[0].done():
            self._futures.append(asyncio.Future())
        self._futures[-1].set_result(event)

    async def wait_for_message(self, timeout=None):
        """
        wait for message pushed to the server
        """
        if not self._futures:
            self._futures.append(asyncio.Future())
        # always wait for the first event
        result = await asyncio.wait_for(self._futures[0], timeout=timeout)
        # Remove it and return the result
        self._futures.popleft()
        return [result]

    async def version_history(self, _):
        """
        Provide a fake api version list
        """
        return web.json_response([{'version': f'{i}.0'}
                                  for i in range(35, 43)])

    async def cometd(self, request):
        """
        Simulate CometD connection strategy
        """
        # We should be authenticate
        if request.headers.get('Authorization', None) != 'Bearer my-token':
            return web.Response(status=403)

        # Extract message
        message = await request.json()
        self.received_messages.append(message)
        channel = message['channel']

        # Only handshake can be check at this step
        if channel == '/meta/handshake':
            return await self.handshake()

        # We can only process other message if the handshake has registred
        # a client id
        if message.get('clientId', None) != self.client_id:
            return web.Response(status=403)

        if channel == '/meta/subscribe':
            return await self.subscribe(message)
        if channel == '/meta/unsubscribe':
            return await self.unsubscribe(message)
        elif channel == '/meta/connect':
            return await self.connect(message)
        elif channel == '/meta/disconnect':
            self.client_id = None
            return web.json_response([{'successful': True}])

        # Unknown channel
        return web.Response(status=404)

    async def handshake(self):
        """
        return handshake response
        """
        # Add an event for timeout advice
        self.push_event({'channel': '/meta/connect', 'advice': {'timeout': 3000}})
        self.client_id = '4'
        return web.json_response([{'clientId': self.client_id}])

    async def subscribe(self, message):
        """
        Subscribe to a channel
        """
        self.subscribed_channels.add(message['subscription'])
        return web.json_response([{'successful': True}])

    async def unsubscribe(self, message):
        """
        Unsubscribe from a channel
        """
        self.subscribed_channels.remove(message['subscription'])
        return web.json_response([{'successful': True}])

    async def connect(self, message):
        """
        Connect and wait for response
        """
        try:
            response = await self.wait_for_message(timeout=1)
            return web.json_response(response)
        except asyncio.TimeoutError:
            return web.Response(status=408)
