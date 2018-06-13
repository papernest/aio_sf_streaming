"""
Test basic flow
"""
import datetime
from collections import namedtuple
import asyncio

import pytest

from aio_sf_streaming import SimpleSalesforceStreaming
from ..utils.async_itertools import async_enumerate
from ..utils.async_tools import wait_until_all_completed


# ==================== Test client ====================

class Replay(namedtuple('Replay', 'channel replay_id creation_time')):
    """
    Record a Replay message
    """


class MyTestClient(SimpleSalesforceStreaming):
    def __init__(self, **kwargs):
        self.stored_replay = set()
        super().__init__(**kwargs)

    async def store_replay_id(self, channel, replay_id, creation_time):
        self.stored_replay.add(Replay(channel, replay_id, creation_time))

    async def get_last_replay_id(self, channel):
        elements = {r for r in self.stored_replay if r.channel == channel}
        if not elements:
            return None
        return max(elements, key=lambda r: r.creation_time)


async def send_events(count, sleep, channel, server):
    """
    Allow to send fake event to the server
    """
    for i in range(count):
        await asyncio.sleep(sleep)
        server.push_result(channel, {"foo": i})


@pytest.mark.asyncio
async def test_basic_flow(event_loop, fake_sf_session):
    # Launch our streaming client for few events

    received_messages = []
    async with MyTestClient(username="my-username",
                            password="my-password",
                            client_id="my-client_id",
                            client_secret="my-client_secret",
                            loop=event_loop,
                            login_connector=fake_sf_session['login_connector'],
                            connector=fake_sf_session['connector']) as sfs:
        await sfs.subscribe('/topic/Foo')
        await sfs.subscribe('/topic/Bar')
        # Push messages from server
        event_loop.create_task(send_events(2, 1, '/topic/Foo', fake_sf_session['sf_server']))
        event_loop.create_task(send_events(2, 1.5, '/topic/Bar', fake_sf_session['sf_server']))

        async for i, message in async_enumerate(sfs.events()):
            received_messages.append(message)
            if i == 3:
                await sfs.unsubscribe('/topic/Foo')
                await sfs.unsubscribe('/topic/Bar')
                await sfs.ask_stop()

    await wait_until_all_completed()

    # check results
    assert received_messages == [{
        'data': {
            'sobject': {
                'foo': 0
            },
            'event': {
                'replayId': 1,
                'createdDate': '2018-03-15T13:42:01'
            }
        },
        'channel': '/topic/Foo'
    }, {
        'data': {
            'sobject': {
                'foo': 0
            },
            'event': {
                'replayId': 1,
                'createdDate': '2018-03-15T13:42:02'
            }
        },
        'channel': '/topic/Bar'
    }, {
        'data': {
            'sobject': {
                'foo': 1
            },
            'event': {
                'replayId': 2,
                'createdDate': '2018-03-15T13:42:03'
            }
        },
        'channel': '/topic/Foo'
    }, {
        'data': {
            'sobject': {
                'foo': 1
            },
            'event': {
                'replayId': 2,
                'createdDate': '2018-03-15T13:42:04'
            }
        },
        'channel': '/topic/Bar'
    }]

    assert fake_sf_session['sf_server'].received_messages == [
        {
            'channel': '/meta/handshake',
            'supportedConnectionTypes': ['long-polling'],
            'version': '1.0',
            'minimumVersion': '1.0',
            'ext': {
                'replay': True
            },
            'id': '1'
        }, {
            'channel': '/meta/subscribe',
            'subscription': '/topic/Foo',
            'ext': {
                'replay': {
                    '/topic/Foo': -1
                }
            },
            'id': '2',
            'clientId': '4'
        }, {
            'channel': '/meta/subscribe',
            'subscription': '/topic/Bar',
            'ext': {
                'replay': {
                    '/topic/Bar': -1
                }
            },
            'id': '3',
            'clientId': '4'
        }, {
            'channel': '/meta/connect',
            'connectionType': 'long-polling',
            'id': '4',
            'clientId': '4'
        }, {
            'channel': '/meta/connect',
            'connectionType': 'long-polling',
            'id': '5',
            'clientId': '4'
        }, {
            'channel': '/meta/connect',
            'connectionType': 'long-polling',
            'id': '6',
            'clientId': '4'
        }, {
            'channel': '/meta/connect',
            'connectionType': 'long-polling',
            'id': '7',
            'clientId': '4'
        }, {
            'channel': '/meta/connect',
            'connectionType': 'long-polling',
            'id': '8',
            'clientId': '4'
        }, {
            'channel': '/meta/unsubscribe',
            'subscription': '/topic/Foo',
            'id': '9',
            'clientId': '4'
        }, {
            'channel': '/meta/unsubscribe',
            'subscription': '/topic/Bar',
            'id': '10',
            'clientId': '4'
        }, {
            'channel': '/meta/disconnect',
            'id': '11',
            'clientId': '4'
        }]

    assert sfs.stored_replay == {
        Replay(
            channel='/topic/Foo',
            replay_id=1,
            creation_time='2018-03-15T13:42:01'),
        Replay(
            channel='/topic/Bar',
            replay_id=2,
            creation_time='2018-03-15T13:42:04'),
        Replay(
            channel='/topic/Bar',
            replay_id=1,
            creation_time='2018-03-15T13:42:02'),
        Replay(
            channel='/topic/Foo',
            replay_id=2,
            creation_time='2018-03-15T13:42:03')
    }
