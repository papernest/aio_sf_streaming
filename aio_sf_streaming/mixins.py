"""
Mixins module: Provide various mixins modules
"""
import asyncio
import enum
import logging
from typing import Union

from .core import JSONList, JSONObject

logger = logging.getLogger("aio_sf_streaming")


class TimeoutAdviceMixin:
    """
    Simple mixin that automatically set timeout setting according to SF
    advice, if provided.
    """

    async def messages(self) -> JSONObject:
        """
        See :py:func:`BaseSalesforceStreaming.messages`
        """
        async for message in super().messages():
            if message.get("channel", "") == "/meta/connect" and "advice" in message:
                timeout_advice = message["advice"].get("timeout", None)
                if timeout_advice:
                    self.timeout = timeout_advice / 1000
            yield message


class ReplayType(enum.Enum):
    """
    Enumeration with special replay values
    """

    ALL_EVENTS = -2  #: Replay all events available.
    NEW_EVENTS = -1  #: No replay, retrieve only new events.


class ReplayMixin:
    """
    Mixing adding replay support to the streaming client.

    This mixin is not enough, you must implement :py:func:`ReplayMixin.store_replay_id` and
    `:py:func:`ReplayMixin.get_last_replay_id` in a subclass in order to have a working replay.
    """

    async def get_handshake_payload(self) -> JSONObject:
        """
        See :py:func:`BaseSalesforceStreaming.get_handshake_payload`
        """
        payload = await super().get_handshake_payload()
        # Activate replay extension
        payload.setdefault("ext", {}).update({"replay": True})
        return payload

    async def get_subscribe_payload(self, channel: str) -> JSONObject:
        """
        See :py:func:`BaseSalesforceStreaming.get_subscribe_payload`
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
        payload.setdefault("ext", {}).setdefault("replay", {})
        payload["ext"]["replay"][channel] = replay_id

        return payload

    async def messages(self) -> JSONObject:
        """
        See :py:func:`BaseSalesforceStreaming.messages`
        """
        async for message in super().messages():
            channel = message["channel"]

            # On new message, call callback to store replay id
            if not channel.startswith("/meta/"):
                event = message["data"]["event"]
                replay_id = event["replayId"]
                creation_time = event["createdDate"]

                # Create a task : do not wait the replay id is stored to
                # reconnect as soon as possible
                self.loop.create_task(self.store_replay_id(channel, replay_id, creation_time))
            yield message

    async def store_replay_id(self, channel: str, replay_id: int, creation_time: str) -> None:
        """
        Callback called to store a replay id. You should override this method
        to implement your custom logic.

        :param channel: Channel name
        :param replay_id: replay id to store
        :param creation_time: Creation time. You should store only the last
            created object but you can not know if you received event in order
            without this. This value is the string provided by SF.
        """

    async def get_last_replay_id(self, channel: str) -> Union[ReplayType, int]:
        """
        Callback called to retrieve a replay id. You should override this method
        to implement your custom logic.

        :param channel: Channel name
        """


class AutoVersionMixin:
    """
    Simple mixin that fetch last api version before connect.
    """

    async def handshake(self) -> JSONList:
        """
        See :py:func:`BaseSalesforceStreaming.handshake`
        """
        # Get last api version
        data = await self.get("/services/data/")
        try:
            self.version = data[-1]["version"]
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

    async def start(self) -> None:
        """
        See :py:func:`BaseSalesforceStreaming.start`
        """
        self._subchannels = set()
        await super().start()

    async def subscribe(self, channel: str) -> JSONList:
        """
        See :py:func:`BaseSalesforceStreaming.subscribe`
        """
        self._subchannels.add(channel)
        return await super().subscribe(channel)

    async def messages(self) -> JSONObject:
        """
        See :py:func:`BaseSalesforceStreaming.messages`
        """
        async for message in super().messages():
            channel = message["channel"]

            # If asked, perform a new handshake
            if channel.startswith("/meta/") and message.get("error") == "403::Unknown client":
                logger.info("Disconnected, do new handshake")
                await self.handshake()
                continue

            yield message

    async def unsubscribe(self, channel: str) -> JSONList:
        """
        See :py:func:`BaseSalesforceStreaming.unsubscribe`
        """
        self._subchannels.remove(channel)
        return await super().unsubscribe(channel)

    async def stop(self) -> None:
        """
        See :py:func:`BaseSalesforceStreaming.stop`
        """
        await super().stop()
        self._subchannels = None

    async def handshake(self) -> JSONList:
        """
        See :py:func:`BaseSalesforceStreaming.handshake`
        """
        response = await super().handshake()

        # If we reconnect, we must re-subscribe to all channels
        for channel in self._subchannels:
            self.loop.create_task(super().subscribe(channel))

        return response


class ReSubscribeMixin:
    """
    Mixin that handle subscription error, will try again after a short delay

    :param retry_sub_duration: Duration between subscribe retry if server is
        too buzy (initial value).
    :param retry_factor: Factor amplification between each successive retry
    :param retry_max_duration: Maximum value of the retry duration
    :param retry_max_count: Maximum count of retry, after this count is reach,
        response or exception are propagated.
    """

    def __init__(
        self,
        retry_sub_duration: float = 0.1,
        retry_factor: float = 1.,
        retry_max_duration: float = 30.,
        retry_max_count: int = 20,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.retry_sub_duration = retry_sub_duration
        self.retry_factor = retry_factor
        self.retry_max_duration = retry_max_duration
        self.retry_max_count = retry_max_count
        self.retry_current_duration = {}
        self.retry_current_count = {}

    async def should_retry_on_exception(self, channel: str, exception: Exception) -> bool:
        """
        Callback called to process an exception raised during subscription.
        Return a boolean if we must retry. If ``False`` is returned, the exception will be
        propagated to caller.

        By-default, do return always ``False``.

        :param channel: Channel name
        :param exception: The exception raised
        """
        return False

    async def should_retry_on_error_response(self, channel: str, response: JSONObject) -> bool:
        """
        Callback called to process a response with and error message.
        Return a boolean if we must retry. If ``False`` is returned, the response will be
        returned to caller.

        By-default, retry on known 'server unavailable' response.

        :param channel: Channel name
        :param response: The response received
        """
        return (
            response[0]
            .get("ext", {})
            .get("sfdc", {})
            .get("failureReason", "")
            .startswith("SERVER_UNAVAILABLE")
        )

    def _update_retry_count(self, channel: str) -> bool:
        """
        Update retry count for the channel. Return a boolean if we should retry
        """
        self.retry_current_count[channel] = self.retry_current_count.get(channel, 0) + 1
        if self.retry_current_count[channel] >= self.retry_max_count:
            return False
        duration = self.retry_current_duration.get(channel, -1)
        if duration < 0:
            duration = self.retry_sub_duration
        else:
            duration = min(duration * self.retry_factor, self.retry_max_count)
        self.retry_current_duration[channel] = duration
        return True

    async def subscribe(self, channel: str) -> JSONList:
        """
        See :py:func:`BaseSalesforceStreaming.subscribe`
        """
        while True:
            try:
                response = await super().subscribe(channel)
            except Exception as e:
                should_retry = await self.should_retry_on_exception(channel, e)
                if should_retry:
                    should_retry = self._update_retry_count(channel)
                if not should_retry:
                    raise
            else:
                if response and response[0]["successful"]:
                    should_retry = False
                else:
                    should_retry = await self.should_retry_on_error_response(channel, response)
                    if should_retry:
                        should_retry = self._update_retry_count(channel)

            if not should_retry:
                self.retry_current_duration[channel] = -1
                self.retry_current_count[channel] = 0
                return response

            await asyncio.sleep(self.retry_current_duration[channel])


class AllMixin(
    TimeoutAdviceMixin,  # Use SF timeout advice
    AutoVersionMixin,  # Auto-fetch last api version
    ReplayMixin,  # Add replay support
    AutoReconnectMixin,  # Add auto-reconnection feature
    ReSubscribeMixin,
):  # Handle subscription errors
    """
    Helper class to add all mixin with one class
    """
