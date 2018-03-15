"""
Mixins module: Provide various mixins modules
"""
import asyncio
import enum
import logging

from .utils import parse_sf_datetime

logger = logging.getLogger('aio_sf_streaming')


class TimeoutAdviceMixin:
    """
    Simple mixin that set timeout setting according to SF advice if provided
    """

    async def messages(self):
        """
            Return all messages and retrieve timeout advice if available
        """
        async for message in super().messages():
            if (message.get('channel', '') == '/meta/connect'
                    and 'advice' in message):
                timeout_advice = message['advice'].get('timeout', None)
                if timeout_advice:
                    self.timeout = timeout_advice / 1000
            yield message


class ReplayType(enum.Enum):
    """
    Special replay values
    """
    ALL_EVENTS = -2
    NEW_EVENTS = -1


class ReplayMixin:
    """
    Mixing adding replay support to the streaming client.

    This mixin is not enough, you must implement ``store_replay_id`` and
    ``get_last_replay_id`` in a subclass in order to have a working replay.
    """

    async def get_handshake_payload(self):
        """
        Provide the handshake payload
        """
        payload = await super().get_handshake_payload()
        # Activate replay extension
        payload.setdefault('ext', {}).update({'replay': True})
        return payload

    async def get_subscribe_payload(self, channel):
        """
        Provide the subscription payload for a specific channel
        """
        payload = await super().get_subscribe_payload(channel)

        # Call inner callback to retrieve the last replay id
        replay_id = await self.get_last_replay_id(channel)

        # No response => Use only new events (default behavior)
        if not replay_id:
            replay_id = ReplayType.NEW_EVENTS

        # Extract replay value
        if isinstance(replay_id, ReplayType):
            replay_id = replay_id.value
        replay_id = int(replay_id)

        # Update payload
        payload.setdefault('ext', {}).setdefault('replay', {})
        payload['ext']['replay'][channel] = replay_id

        return payload

    async def messages(self):
        """
            Return all message
        """
        async for message in super().messages():
            channel = message['channel']

            # On new message, call callback to store replay id
            if not channel.startswith('/meta/'):
                event = message['data']['event']
                replay_id = event['replayId']
                creation_time = parse_sf_datetime(event['createdDate'])

                # Create a task : do not wait the replay id is stored to
                # reconnect as soon as possible
                self.loop.create_task(
                    self.store_replay_id(channel, replay_id, creation_time))
            yield message

    async def store_replay_id(self, channel, replay_id, creation_time):
        """
        Callback called to store a replay id
        """

    async def get_last_replay_id(self, channel):
        """
        Callback called to retrieve a replay id
        """


class AutoVersionMixin:
    """
    Simple mixin that fetch last api version before connect
    """

    async def handshake(self):
        """
        Coroutine that perform an handshake (mandatory before any other action)

        Fetch last api version on startup.
        """
        # Get last api version
        data = await self.get('/services/data/')
        try:
            self.version = data[-1]['version']
        except (IndexError, KeyError):
            pass
        logger.info("API version used: %r", self.version)

        return await super().handshake()


class AutoReconnectMixin:
    """
    Mixin that will automatically reconnect when asked by Salesforce
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Used to store all subscribed channels
        self._subchannels = None

    async def start(self):
        """
        Helper method doing all starting call
        """
        self._subchannels = set()
        await super().start()

    async def subscribe(self, channel):
        """
        Subscribe to a channel
        """
        self._subchannels.add(channel)
        return await super().subscribe(channel)

    async def messages(self):
        """
        Return all messages
        """
        async for message in super().messages():
            channel = message['channel']

            # If asked, perform a new handshake
            if (channel.startswith('/meta/') and
                    message.get('error') == '403::Unknown client'):
                logger.info("Disconnected, do new handshake")
                await self.handshake()
                continue

            yield message

    async def unsubscribe(self, channel):
        """
        Unsubscribe to a channel
        """
        self._subchannels.remove(channel)
        return await super().unsubscribe(channel)

    async def stop(self):
        """
        Helper method doing all stopping call
        """
        await super().stop()
        self._subchannels = None

    async def handshake(self):
        """
        Coroutine that perform an handshake (mandatory before any other action)
        """
        response = await super().handshake()

        # If we reconnect, we must re-subscribe to all channels
        for channel in self._subchannels:
            self.loop.create_task(super().subscribe(channel))

        return response


class ReSubscribeMixin:
    """
    Mixin that handle subscription error, will try again after a short delay
    """
    def __init__(self, retry_sub_duration=0.1, **kwargs):
        super().__init__(**kwargs)
        self.retry_sub_duration = retry_sub_duration

    async def subscribe(self, channel):
        """
        Subscribe to a channel and retry after a short duration if asked by SF
        """
        while True:
            response = await super().subscribe(channel)

            if not response or response[0]['successful']:
                return response

            # If not the known error, return
            if not (response[0].get('ext', {})
                               .get('sfdc', {})
                               .get('failureReason', '')
                               .startswith('SERVER_UNAVAILABLE')):
                return response
            await asyncio.sleep(self.retry_sub_duration)
