"""
Some pytest fixture helper
"""
import aiohttp
import pytest

from .utils.fake_server import FakeLoginSfServer, FakeResolver, FakeSfServer


@pytest.fixture()
async def fake_login_server(event_loop):
    """
    Fixture: create a fake login server
    """
    fake_sf = FakeLoginSfServer(loop=event_loop)
    await fake_sf.start()
    yield fake_sf
    await fake_sf.stop()


@pytest.fixture()
async def fake_sf_server(event_loop):
    """
    Fixture: create a fake sf server
    """
    fake_sf = FakeSfServer(loop=event_loop)
    await fake_sf.start()
    yield fake_sf
    await fake_sf.stop()


@pytest.fixture()
async def fake_sf_session(event_loop, fake_sf_server, fake_login_server):
    """
    Fixture: create a fake sf session
    """
    # Merge all fake server hosts
    info = {**fake_sf_server.host_mapping, **fake_login_server.host_mapping}
    resolver = FakeResolver(info, loop=event_loop)
    # We need one connector by connection
    connector = aiohttp.TCPConnector(
        loop=event_loop, resolver=resolver, verify_ssl=False
    )
    login_connector = aiohttp.TCPConnector(
        loop=event_loop, resolver=resolver, verify_ssl=False
    )
    # Return all data
    yield {
        "login_connector": login_connector,
        "connector": connector,
        "login_server": fake_login_server,
        "sf_server": fake_sf_server,
    }
