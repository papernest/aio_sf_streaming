"""
Unit tests for BaseSalesforceStreaming flow methods
"""
import asyncio
from unittest.mock import call

import aiohttp
from asynctest import patch, CoroutineMock
import pytest

from aio_sf_streaming import BaseSalesforceStreaming
from ..utils.async_itertools import async_enumerate


class SfStreamingTestClass(BaseSalesforceStreaming):
    """
    A fake sf streaming derivated class that always return a fake token
    """
    TEST_ACCESS_TOKEN = "42"
    TEST_INSTANCE_URL = 'https://my-instance.com'

    async def fetch_token(self):
        return self.TEST_ACCESS_TOKEN, self.TEST_INSTANCE_URL


@patch('aio_sf_streaming.BaseSalesforceStreaming.create_connected_session')
@patch('aio_sf_streaming.BaseSalesforceStreaming.handshake')
@pytest.mark.asyncio
async def test_start(mock_handshake, mock_create_session):
    """
    Test start method : should create a session and perform handshake
    """

    client = SfStreamingTestClass()
    await client.start()

    assert mock_create_session.call_count == 1
    assert mock_create_session.call_args == call()

    assert mock_handshake.call_count == 1
    assert mock_handshake.call_args == call()


@patch('aio_sf_streaming.BaseSalesforceStreaming.get_subscribe_payload')
@patch('aio_sf_streaming.BaseSalesforceStreaming.send')
@pytest.mark.asyncio
async def test_subscribe(mock_send, mock_sub_payload):
    """
    Test subscribe method : should retrieve payload, send subscribtion message
    and return the response
    """
    sub_payload = {"channel": "foo"}
    mock_sub_payload.return_value = sub_payload

    send_response = {"succeful": True}
    mock_send.return_value = send_response

    client = SfStreamingTestClass()
    ret = await client.subscribe("foo")

    assert mock_sub_payload.call_count == 1
    assert mock_sub_payload.call_args == call("foo")

    assert mock_send.call_count == 1
    assert mock_send.call_args == call(sub_payload)

    assert ret == send_response


@patch('aio_sf_streaming.BaseSalesforceStreaming.send')
@pytest.mark.asyncio
async def test_messages(mock_send):
    """
    Test messages method : should send connect message and yield results.
    Should reconnect after yield result or timeouts.
    """
    messages = [
        {"channel": '/topic/Foo0'},
        {"channel": '/meta/connect'},
        {"channel": '/topic/Foo1'},
        {"channel": '/topic/Foo2'},
        {"channel": '/topic/Foo3'},
        {"channel": '/topic/Foo4'},
        {"channel": '/meta/connect'},
        {"channel": '/topic/Foo5'},
        {"channel": '/meta/connect'},
    ]
    mock_send.side_effect = [
        # First message : a simple success
        [messages[0]],
        # Timeout
        aiohttp.ClientResponseError(None, None, code=408),
        # Second message : multiples messages
        messages[1:4],
        # Timeout
        asyncio.TimeoutError(),
        # Other messages
        messages[4:]]

    client = SfStreamingTestClass()
    received_messages = []
    # We iterate message and ask stop after received 7 messages
    async for i, m in async_enumerate(client.messages()):
        received_messages.append(m)
        if i == 6:
            await client.ask_stop()

    # We should have only 7 messages
    assert received_messages == messages[:7]
    assert mock_send.call_count == 5

    client = SfStreamingTestClass()
    # An other error shoud be re-raised
    mock_send.side_effect = [
        aiohttp.ClientResponseError(None, None, code=404),
    ]
    with pytest.raises(aiohttp.ClientResponseError):
        async for m in client.messages():
            # Avoid infinite loop if test fail
            assert False


@patch('aio_sf_streaming.BaseSalesforceStreaming.send')
@pytest.mark.asyncio
async def test_events(mock_send):
    """
    Test events method : same as messages but skip 'meta' messages
    """
    messages = [
        {"channel": '/topic/Foo0'},
        {"channel": '/meta/connect'},
        {"channel": '/topic/Foo1'},
        {"channel": '/topic/Foo2'},
        {"channel": '/topic/Foo3'},
        {"channel": '/topic/Foo4'},
        {"channel": '/meta/connect'},
        {"channel": '/topic/Foo5'},
        {"channel": '/meta/connect'},
    ]
    mock_send.side_effect = [
        # First message : a simple success
        [messages[0]],
        # Second message : multiples messages
        messages[1:4],
        # Timeout
        asyncio.TimeoutError(),
        # Other messages
        messages[4:]]

    client = SfStreamingTestClass()
    received_messages = []
    # We iterate message and ask stop after received 6 messages
    async for i, m in async_enumerate(client.events()):
        received_messages.append(m)
        if i == 5:
            await client.ask_stop()

    # We should have only 6 messages, thus without meta
    excepted_messages = [m for m in messages if m["channel"] != '/meta/connect']
    assert received_messages == excepted_messages
    assert mock_send.call_count == 4


@patch('aio_sf_streaming.BaseSalesforceStreaming.get_unsubscribe_payload')
@patch('aio_sf_streaming.BaseSalesforceStreaming.send')
@pytest.mark.asyncio
async def test_unsubscribe(mock_send, mock_unsub_payload):
    """
    Test unsubscribe method : should retrieve payload, send unsubscribtion message
    and return the response
    """
    unsub_payload = {"channel": "foo"}
    mock_unsub_payload.return_value = unsub_payload

    send_response = {"succeful": True}
    mock_send.return_value = send_response

    client = SfStreamingTestClass()
    ret = await client.unsubscribe("foo")

    assert mock_unsub_payload.call_count == 1
    assert mock_unsub_payload.call_args == call("foo")

    assert mock_send.call_count == 1
    assert mock_send.call_args == call(unsub_payload)

    assert ret == send_response


@patch('aio_sf_streaming.BaseSalesforceStreaming.ask_stop')
@patch('aio_sf_streaming.BaseSalesforceStreaming.disconnect')
@patch('aio_sf_streaming.BaseSalesforceStreaming.close_session')
@pytest.mark.asyncio
async def test_close(mock_close_session, mock_disconnect, mock_ask_stop):
    """
    Test stop method : should ask stopping, disconnect from cometd and close
    connection
    """
    client = SfStreamingTestClass()
    await client.stop()

    assert mock_ask_stop.call_count == 1
    assert mock_ask_stop.call_args == call()

    assert mock_disconnect.call_count == 1
    assert mock_disconnect.call_args == call()

    assert mock_close_session.call_count == 1
    assert mock_close_session.call_args == call()


def test_token_url():
    """
    Test token url property
    """
    assert (SfStreamingTestClass(sandbox=True).token_url ==
            'https://test.salesforce.com/services/oauth2/token')
    assert (SfStreamingTestClass(sandbox=False).token_url ==
            'https://login.salesforce.com/services/oauth2/token')
    assert (SfStreamingTestClass().token_url ==
            'https://login.salesforce.com/services/oauth2/token')


@patch('aiohttp.ClientSession')
@pytest.mark.asyncio
async def test_create_connected_session(mock_client_session):
    """
    Test create_connected_session: Should create an aiohttp client session
    using provided session and set provided instance_url
    """
    client = SfStreamingTestClass()
    result = await client.create_connected_session()

    assert client.instance_url == SfStreamingTestClass.TEST_INSTANCE_URL

    assert mock_client_session.call_count == 1
    _, kwargs = mock_client_session.call_args
    assert kwargs['headers']['Authorization'] == 'Bearer 42'

    assert result is mock_client_session()


@pytest.mark.asyncio
async def test_close_session():
    """
    Test close session: Call close session if defined
    """
    client = SfStreamingTestClass()
    with patch.object(client, 'session') as mock_session:
        mock_session_close = CoroutineMock()
        mock_session.close = mock_session_close
        await client.close_session()

    assert mock_session_close.call_count == 1
    assert client.session is None

    # An other one to check that it does not generate errors
    await client.close_session()
    assert mock_session_close.call_count == 1
    assert client.session is None


def test_end_point():
    """
    Test end point property depending of the provided version
    """
    assert SfStreamingTestClass(version='1.0').end_point == '/cometd/1.0/'
    assert SfStreamingTestClass(version='42.0').end_point == '/cometd/42.0/'
    assert SfStreamingTestClass().end_point == '/cometd/42.0/'


@pytest.mark.asyncio
async def test_handshake_payload():
    """
    Test handshake_payload
    """
    client = SfStreamingTestClass()
    # the handshake payload is constant
    payload = await client.get_handshake_payload()

    assert payload == {
            'channel': '/meta/handshake',
            'supportedConnectionTypes': ['long-polling'],
            'version': '1.0',
            'minimumVersion': '1.0'}


@pytest.mark.asyncio
async def test_subscribe_payload():
    """
    Test subscribe payload
    """
    client = SfStreamingTestClass()
    payload = await client.get_subscribe_payload('/topic/Foo')

    assert payload == {
        'channel': '/meta/subscribe',
        'subscription': '/topic/Foo'
    }


@pytest.mark.asyncio
async def test_unsubscribe_payload():
    """
    Test unsubscribe payload
    """
    client = SfStreamingTestClass()
    payload = await client.get_unsubscribe_payload('/topic/Foo')

    assert payload == {
        'channel': '/meta/unsubscribe',
        'subscription': '/topic/Foo'
    }


@patch('aio_sf_streaming.BaseSalesforceStreaming.send')
@pytest.mark.asyncio
async def test_handhshake(mock_send):
    """
    Test handshake: should send handshake_payload, set client id and return
    provided response
    """
    send_response = [{"succeful": True, 'clientId': 'Foo'}]
    mock_send.return_value = send_response

    client = SfStreamingTestClass()
    ret = await client.handshake()

    assert mock_send.call_count == 1
    assert mock_send.call_args == call({
            'channel': '/meta/handshake',
            'supportedConnectionTypes': ['long-polling'],
            'version': '1.0',
            'minimumVersion': '1.0'})

    assert ret == send_response
    assert client.client_id == 'Foo'


@patch('aio_sf_streaming.BaseSalesforceStreaming.send')
@pytest.mark.asyncio
async def test_disconnect(mock_send):
    """
    Test disconnect: should send diconnect
    """
    send_response = {"succeful": True}
    mock_send.return_value = send_response

    client = SfStreamingTestClass()
    ret = await client.disconnect()

    assert mock_send.call_count == 1
    assert mock_send.call_args == call({'channel': '/meta/disconnect'})

    assert ret == send_response


@patch('aio_sf_streaming.BaseSalesforceStreaming.post')
@pytest.mark.asyncio
async def test_send(mock_post):
    """
    Test send: complete payload and post response
    """
    post_response = {"succeful": True}
    mock_post.return_value = post_response

    # Without client_id
    client = SfStreamingTestClass()
    client.message_count = 41
    client.client_id = None
    ret = await client.send({'foo': 'bar'})

    assert mock_post.call_count == 1
    assert mock_post.call_args == call(client.end_point,
                                       json={'foo': 'bar', 'id': '42'})
    assert ret == post_response

    # With client_id
    assert client.message_count == 42
    client.client_id = 'buzz'
    ret = await client.send({'foo2': 'bar2'})

    assert mock_post.call_count == 2
    assert mock_post.call_args == call(client.end_point,
                                       json={'foo2': 'bar2',
                                             'clientId': 'buzz',
                                             'id': '43'})
    assert ret == post_response


@patch('aio_sf_streaming.BaseSalesforceStreaming.request')
@pytest.mark.asyncio
async def test_get(mock_request):
    """
    Test get: helper for request
    """
    request_response = {"succeful": True}
    mock_request.return_value = request_response

    client = SfStreamingTestClass()
    response = await client.get('/foo', params={'q': 'test'})

    assert response == request_response
    assert mock_request.call_count == 1
    assert mock_request.call_args == call('get', '/foo', params={'q': 'test'})


@patch('aio_sf_streaming.BaseSalesforceStreaming.request')
@pytest.mark.asyncio
async def test_post(mock_request):
    """
    Test post: helper for request
    """
    request_response = {"succeful": True}
    mock_request.return_value = request_response

    client = SfStreamingTestClass()
    response = await client.post('/foo', json={'q': 'test'})

    assert response == request_response
    assert mock_request.call_count == 1
    assert mock_request.call_args == call('post', '/foo', json={'q': 'test'})


@patch('aio_sf_streaming.BaseSalesforceStreaming.start')
@patch('aio_sf_streaming.BaseSalesforceStreaming.stop')
@pytest.mark.asyncio
async def test_ctx_manager(mock_stop, mock_start):
    """
    Test context manager interface
    """

    async with SfStreamingTestClass() as client:
        assert mock_start.call_count == 1
        assert isinstance(client, SfStreamingTestClass)
        assert mock_stop.call_count == 0
    assert mock_stop.call_count == 1

    try:
        async with SfStreamingTestClass() as client:
            assert mock_start.call_count == 2
            assert mock_stop.call_count == 1
            raise Exception()
    except Exception:
        assert mock_stop.call_count == 2
