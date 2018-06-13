"""
Unit tests for connectors flow
"""

import asyncio
import datetime as dt
from math import isclose
from unittest.mock import call

from asynctest import patch, CoroutineMock
import pytest

from aio_sf_streaming import (
    BaseSalesforceStreaming,
    TimeoutAdviceMixin,
    ReplayMixin,
    ReplayType,
    AutoVersionMixin,
    AutoReconnectMixin,
    ReSubscribeMixin,
)
from ..utils.async_itertools import async_enumerate
from ..utils.async_tools import wait_until_all_completed


class TimeoutTestClass(TimeoutAdviceMixin, BaseSalesforceStreaming):
    """
    A fake sf streaming derivated class that always return a fake token
    """

    TEST_ACCESS_TOKEN = "42"
    TEST_INSTANCE_URL = "https://my-instance.com"

    async def fetch_token(self):
        return self.TEST_ACCESS_TOKEN, self.TEST_INSTANCE_URL


@patch("aio_sf_streaming.BaseSalesforceStreaming.send")
@pytest.mark.asyncio
async def test_timeout_advice(mock_send):
    """
    Test timeout advice mixin
    """

    messages = [
        {"channel": "/meta/connect", "advice": {"timeout": 42000}},
        {"channel": "/topic/Foo0"},
        {"channel": "/topic/Foo1"},
        {"channel": "/topic/Foo2"},
        {"channel": "/topic/Foo3"},
        {"channel": "/topic/Foo4"},
        {"channel": "/meta/connect"},
        {"channel": "/topic/Foo5"},
        {"channel": "/meta/connect"},
    ]
    mock_send.side_effect = [
        # First message : a simple success
        [messages[0]],
        # Second message : multiples messages
        messages[1:4],
        # Timeout
        asyncio.TimeoutError(),
        # Other messages
        messages[4:],
    ]
    client = TimeoutTestClass()
    old_timeout = client.timeout
    received_messages = []
    # We iterate message and ask stop after received 7 messages
    async for i, m in async_enumerate(client.messages()):
        received_messages.append(m)
        if i == 6:
            await client.ask_stop()

    # We should have only 7 messages
    assert received_messages == messages[:7]
    assert mock_send.call_count == 4

    # Timeout advice should be used
    new_timeout = client.timeout
    assert new_timeout is not old_timeout
    assert isclose(new_timeout, 42.)


class ReplayTestClass(ReplayMixin, BaseSalesforceStreaming):
    """
    A fake sf streaming derivated class that always return a fake token
    """

    TEST_ACCESS_TOKEN = "42"
    TEST_INSTANCE_URL = "https://my-instance.com"

    async def fetch_token(self):
        return self.TEST_ACCESS_TOKEN, self.TEST_INSTANCE_URL


@pytest.mark.asyncio
async def test_replay_handshake_payload():
    """
    Test replay handshake_payload
    """
    client = ReplayTestClass()
    # the handshake payload is constant
    payload = await client.get_handshake_payload()

    assert "ext" in payload
    assert payload["ext"].get("replay") is True


@patch.object(ReplayTestClass, "get_last_replay_id")
@pytest.mark.asyncio
async def test_replay_subscribe_payload(mock_last_id):
    """
    Test replay subscribe_payload
    """
    client = ReplayTestClass()

    # By default, new events
    mock_last_id.return_value = None
    mock_last_id.reset_mock()
    result = await client.get_subscribe_payload("/topic/Foo")
    assert mock_last_id.call_count == 1
    assert result["ext"]["replay"]["/topic/Foo"] == -1

    # ReplayType.NEW_EVENTS => -1
    mock_last_id.return_value = ReplayType.NEW_EVENTS
    mock_last_id.reset_mock()
    result = await client.get_subscribe_payload("/topic/Foo")
    assert mock_last_id.call_count == 1
    assert result["ext"]["replay"]["/topic/Foo"] == -1

    # ReplayType.ALL_EVENTS => -2
    mock_last_id.return_value = ReplayType.ALL_EVENTS
    mock_last_id.reset_mock()
    result = await client.get_subscribe_payload("/topic/Foo")
    assert mock_last_id.call_count == 1
    assert result["ext"]["replay"]["/topic/Foo"] == -2

    # Specific value : used directly
    mock_last_id.return_value = 42
    mock_last_id.reset_mock()
    result = await client.get_subscribe_payload("/topic/Foo")
    assert mock_last_id.call_count == 1
    assert result["ext"]["replay"]["/topic/Foo"] == 42


@patch.object(ReplayTestClass, "store_replay_id")
@patch("aio_sf_streaming.BaseSalesforceStreaming.send")
@pytest.mark.asyncio
async def test_replay_message(mock_send, mock_store_replay):
    """
    Test replay message: should send replay id to a the callback
    """

    messages = [
        {
            "channel": "/topic/Foo0",
            "data": {"event": {"replayId": 1, "createdDate": "2018-03-14T11:58:42.1234Z"}},
        },
        {
            "channel": "/topic/Foo1",
            "data": {"event": {"replayId": 1, "createdDate": "2018-03-14T11:58:43.1234Z"}},
        },
        {
            "channel": "/topic/Foo0",
            "data": {"event": {"replayId": 2, "createdDate": "2018-03-14T11:58:44.1234Z"}},
        },
        {
            "channel": "/topic/Foo1",
            "data": {"event": {"replayId": 2, "createdDate": "2018-03-14T11:58:45.1234Z"}},
        },
        {
            "channel": "/topic/Foo2",
            "data": {"event": {"replayId": 1, "createdDate": "2018-03-14T11:58:46.1234Z"}},
        },
        {
            "channel": "/topic/Foo0",
            "data": {"event": {"replayId": 3, "createdDate": "2018-03-14T11:58:47.1234Z"}},
        },
        {
            "channel": "/topic/Foo0",
            "data": {"event": {"replayId": 4, "createdDate": "2018-03-14T11:58:48.1234Z"}},
        },
        {
            "channel": "/topic/Foo1",
            "data": {"event": {"replayId": 3, "createdDate": "2018-03-14T11:58:49.1234Z"}},
        },
        {
            "channel": "/topic/Foo0",
            "data": {"event": {"replayId": 5, "createdDate": "2018-03-14T11:58:50.1234Z"}},
        },
        {
            "channel": "/topic/Foo1",
            "data": {"event": {"replayId": 4, "createdDate": "2018-03-14T11:58:51.1234Z"}},
        },
        {
            "channel": "/topic/Foo2",
            "data": {"event": {"replayId": 2, "createdDate": "2018-03-14T11:58:52.1234Z"}},
        },
        {
            "channel": "/topic/Foo0",
            "data": {"event": {"replayId": 6, "createdDate": "2018-03-14T11:58:53.1234Z"}},
        },
        {"channel": "/meta/connect"},
        {"channel": "/meta/connect"},
    ]
    mock_send.side_effect = [
        # First message : a simple success
        [messages[0]],
        # Second message : multiples messages
        messages[1:4],
        # Other messages
        messages[4:-2],
        [messages[-2]],
        [messages[-1]],
    ]
    client = ReplayTestClass()
    async for i, m in async_enumerate(client.messages()):
        assert m == messages[i]
        if i == len(messages) - 2:
            await client.ask_stop()
    await wait_until_all_completed()
    assert mock_store_replay.call_count == 12
    assert mock_store_replay.mock_calls == [
        call("/topic/Foo0", 1, "2018-03-14T11:58:42.1234Z"),
        call("/topic/Foo1", 1, "2018-03-14T11:58:43.1234Z"),
        call("/topic/Foo0", 2, "2018-03-14T11:58:44.1234Z"),
        call("/topic/Foo1", 2, "2018-03-14T11:58:45.1234Z"),
        call("/topic/Foo2", 1, "2018-03-14T11:58:46.1234Z"),
        call("/topic/Foo0", 3, "2018-03-14T11:58:47.1234Z"),
        call("/topic/Foo0", 4, "2018-03-14T11:58:48.1234Z"),
        call("/topic/Foo1", 3, "2018-03-14T11:58:49.1234Z"),
        call("/topic/Foo0", 5, "2018-03-14T11:58:50.1234Z"),
        call("/topic/Foo1", 4, "2018-03-14T11:58:51.1234Z"),
        call("/topic/Foo2", 2, "2018-03-14T11:58:52.1234Z"),
        call("/topic/Foo0", 6, "2018-03-14T11:58:53.1234Z"),
    ]


class AutoVersionTestClass(AutoVersionMixin, BaseSalesforceStreaming):
    """
    A fake sf streaming derivated class that always return a fake token
    """

    TEST_ACCESS_TOKEN = "42"
    TEST_INSTANCE_URL = "https://my-instance.com"

    async def fetch_token(self):
        return self.TEST_ACCESS_TOKEN, self.TEST_INSTANCE_URL


@patch("aio_sf_streaming.BaseSalesforceStreaming.handshake")
@patch("aio_sf_streaming.BaseSalesforceStreaming.get")
@pytest.mark.asyncio
async def test_auto_version(mock_get, mock_handshake):
    """
    Test auto version test
    """
    mock_get.return_value = []
    client = AutoVersionTestClass(version="1.0")

    # get should be called but version not updated.
    await client.handshake()
    assert mock_get.call_count == 1
    assert mock_get.call_args == call("/services/data/")
    assert client.version == "1.0"
    assert mock_handshake.call_count == 1

    mock_get.return_value = [{"version": "42.0"}]
    mock_get.reset_mock()
    mock_handshake.reset_mock()

    await client.handshake()
    assert mock_get.call_count == 1
    assert mock_get.call_args == call("/services/data/")
    assert client.version == "42.0"
    assert mock_handshake.call_count == 1


class AutoReconnectTestClass(AutoReconnectMixin, BaseSalesforceStreaming):
    """
    A fake sf streaming derivated class that always return a fake token
    """

    TEST_ACCESS_TOKEN = "42"
    TEST_INSTANCE_URL = "https://my-instance.com"

    async def fetch_token(self):
        return self.TEST_ACCESS_TOKEN, self.TEST_INSTANCE_URL


@patch("aio_sf_streaming.BaseSalesforceStreaming.start")
@patch("aio_sf_streaming.BaseSalesforceStreaming.unsubscribe")
@patch("aio_sf_streaming.BaseSalesforceStreaming.stop")
@patch("aio_sf_streaming.BaseSalesforceStreaming.handshake")
@patch("aio_sf_streaming.BaseSalesforceStreaming.subscribe")
@patch("aio_sf_streaming.BaseSalesforceStreaming.send")
@pytest.mark.asyncio
async def test_auto_reconnect(mock_send, mock_subscribe, mock_handshake, *_):
    """
    Test auto reconnect
    """
    client = AutoReconnectTestClass()
    await client.start()
    await client.subscribe("/topic/Foo")
    await client.subscribe("/topic/Bar")
    await client.subscribe("/topic/Baz")

    messages = [
        {"channel": "/topic/Foo"},
        {"channel": "/topic/Foo"},
        {"channel": "/topic/Bar"},
        {"channel": "/topic/Foo"},
        {"channel": "/topic/Baz"},
        {"channel": "/meta/connect", "error": "403::Unknown client"},
        {"channel": "/topic/Baz"},
        {"channel": "/topic/Foo"},
        {"channel": "/topic/Foo"},
        {"channel": "/topic/Bar"},
        {"channel": "/topic/Foo"},
        {"channel": "/meta/connect", "error": "403::Unknown client"},
        {"channel": "/topic/Foo"},
        {"channel": "/topic/Foo"},
        {"channel": "/topic/Bar"},
        {"channel": "/topic/Foo"},
        {"channel": "/meta/connect"},
        {"channel": "/meta/connect"},
    ]
    mock_send.side_effect = [[message] for message in messages]
    j = 0
    async for i, m in async_enumerate(client.messages()):
        if i == 0:
            # First step, only subscribe from test, no specific handhshake
            assert mock_subscribe.call_count == 3
            mock_subscribe.reset_mock()
            assert mock_handshake.call_count == 0
        elif i == 4:
            # nothing new before disconnect
            assert mock_subscribe.call_count == 0
            assert mock_handshake.call_count == 0
        elif i == 5:
            # After a disconnect, handshake and new subscribe has been call
            await wait_until_all_completed()
            assert mock_subscribe.call_count == 3
            assert call("/topic/Foo") in mock_subscribe.mock_calls
            assert call("/topic/Bar") in mock_subscribe.mock_calls
            assert call("/topic/Baz") in mock_subscribe.mock_calls
            mock_subscribe.reset_mock()
            assert mock_handshake.call_count == 1
            mock_handshake.reset_mock()
            j += 1
        elif i == 7:
            # Here, we unsubscribe
            await client.unsubscribe("/topic/Baz")
        elif i == 9:
            # nothing new before disconnect
            assert mock_subscribe.call_count == 0
            assert mock_handshake.call_count == 0
        elif i == 10:
            # After a disconnect, handshake and new subscribe has been call
            await wait_until_all_completed()
            assert mock_subscribe.call_count == 2
            assert call("/topic/Foo") in mock_subscribe.mock_calls
            assert call("/topic/Bar") in mock_subscribe.mock_calls
            mock_subscribe.reset_mock()
            assert mock_handshake.call_count == 1
            mock_handshake.reset_mock()
            j += 1

        assert m == messages[j]
        j += 1
        if i == len(messages) - 4:
            await client.ask_stop()
    await client.stop()


class ReSubscribeTestClass(ReSubscribeMixin, BaseSalesforceStreaming):
    """
    A fake sf streaming derivated class that always return a fake token
    """

    TEST_ACCESS_TOKEN = "42"
    TEST_INSTANCE_URL = "https://my-instance.com"

    async def fetch_token(self):
        return self.TEST_ACCESS_TOKEN, self.TEST_INSTANCE_URL


@patch("aio_sf_streaming.BaseSalesforceStreaming.subscribe")
@pytest.mark.asyncio
async def test_resubscribe(mock_subscribe):
    """
    Test re-subscribe
    """
    mock_subscribe.side_effect = [
        [{"successful": False, "ext": {"sfdc": {"failureReason": "SERVER_UNAVAILABLE"}}}],
        [{"successful": False, "ext": {"sfdc": {"failureReason": "SERVER_UNAVAILABLE"}}}],
        [{"successful": True}],
    ]
    client = ReSubscribeTestClass()
    response = await client.subscribe("/topic/Foo")

    assert response[0]["successful"]
    assert mock_subscribe.call_count == 3


class ReSubscribeCallBackTestClass(ReSubscribeMixin, BaseSalesforceStreaming):
    """
    A fake sf streaming derivated class that always return a fake token
    """

    TEST_ACCESS_TOKEN = "42"
    TEST_INSTANCE_URL = "https://my-instance.com"

    async def fetch_token(self):
        return self.TEST_ACCESS_TOKEN, self.TEST_INSTANCE_URL

    async def should_retry_on_exception(self, channel, exception):
        return isinstance(exception, ValueError)

    async def should_retry_on_error_response(self, channel, response):
        return False


@patch("aio_sf_streaming.BaseSalesforceStreaming.subscribe")
@pytest.mark.asyncio
async def test_resubscribe_callback(mock_subscribe):
    """
    Test re-subscribe
    """
    mock_subscribe.side_effect = [
        ValueError(),
        ValueError(),
        [{"successful": False, "ext": {"sfdc": {"failureReason": "SERVER_UNAVAILABLE"}}}],
    ]
    client = ReSubscribeCallBackTestClass()

    response = await client.subscribe("/topic/Foo")

    assert not response[0]["successful"]
    assert mock_subscribe.call_count == 3
