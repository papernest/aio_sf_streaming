"""
Unit tests for connectors flow
"""

from unittest.mock import call

from asynctest import patch, CoroutineMock
import pytest

from aio_sf_streaming import (PasswordSalesforceStreaming,
                              RefreshTokenSalesforceStreaming)


@patch('aiohttp.ClientSession')
@pytest.mark.asyncio
async def test_password_flow(mock_client_session):
    """
    Test fetch token for password flow
    """
    # Mock client session mock with async context manager.
    # TODO: Found a easier way to create this
    async with mock_client_session() as sm:
        async with sm.post() as rm:
            rm.json = CoroutineMock()
            rm.json.return_value = {
                 'instance_url': 'https://foo.salesforce.com',
                 'token_type': 'Bearer',
                 'access_token': 'my_token'}
    mock_client_session.reset_mock()
    sm.post.reset_mock()

    client = PasswordSalesforceStreaming(
                username="my_username",
                password="my_password",
                client_id="my_client_id",
                client_secret="my_client_secret",
                sandbox=False)
    token, instance_url = await client.fetch_token()

    assert token == 'my_token'
    assert instance_url == 'https://foo.salesforce.com'

    assert mock_client_session.call_count == 1
    _, kwargs = mock_client_session.call_args
    assert "headers" in kwargs
    assert 'Accept' in kwargs["headers"]
    assert kwargs['headers']['Accept'] == 'application/json'

    assert sm.post.call_count == 1
    assert sm.post.call_args == call(
        'https://login.salesforce.com/services/oauth2/token',
        data={
            'grant_type': 'password',
            'username': 'my_username',
            'password': 'my_password',
            'client_id': 'my_client_id',
            'client_secret': 'my_client_secret'})


@patch('aiohttp.ClientSession')
@pytest.mark.asyncio
async def test_refresh_token_flow(mock_client_session):
    """
    Test fetch token for refresh token flow
    """
    # Mock client session mock with async context manager.
    # TODO: Found a easier way to create this
    async with mock_client_session() as sm:
        async with sm.post() as rm:
            rm.json = CoroutineMock()
            rm.json.return_value = {
                 'instance_url': 'https://foo.salesforce.com',
                 'token_type': 'Bearer',
                 'access_token': 'my_token'}
    mock_client_session.reset_mock()
    sm.post.reset_mock()

    client = RefreshTokenSalesforceStreaming(
                refresh_token="refresh_token",
                client_id="my_client_id",
                client_secret="my_client_secret",
                sandbox=False)
    token, instance_url = await client.fetch_token()

    assert token == 'my_token'
    assert instance_url == 'https://foo.salesforce.com'

    assert mock_client_session.call_count == 1
    _, kwargs = mock_client_session.call_args
    assert "headers" in kwargs
    assert 'Accept' in kwargs["headers"]
    assert kwargs['headers']['Accept'] == 'application/json'

    assert sm.post.call_count == 1
    assert sm.post.call_args == call(
        'https://login.salesforce.com/services/oauth2/token',
        data={
            'grant_type': 'refresh_token',
            'refresh_token': 'refresh_token',
            'client_id': 'my_client_id',
            'client_secret': 'my_client_secret'})


def test_missing_parameters():
    """
    Test arguments that must be provided
    """
    with pytest.raises(TypeError):
        PasswordSalesforceStreaming(
            password="my_password",
            client_id="my_client_id",
            client_secret="my_client_secret")

    with pytest.raises(TypeError):
        PasswordSalesforceStreaming(
            username="my_username",
            client_id="my_client_id",
            client_secret="my_client_secret")

    with pytest.raises(TypeError):
        PasswordSalesforceStreaming(
            username="my_username",
            password="my_password",
            client_secret="my_client_secret")

    with pytest.raises(TypeError):
        PasswordSalesforceStreaming(
            username="my_username",
            password="my_password",
            client_id="my_client_id")

    with pytest.raises(TypeError):
        RefreshTokenSalesforceStreaming(
            refresh_token="refresh_token",
            client_secret="my_client_secret")

    with pytest.raises(TypeError):
        RefreshTokenSalesforceStreaming(
            refresh_token="refresh_token",
            client_id="my_client_id")

    with pytest.raises(TypeError):
        RefreshTokenSalesforceStreaming(
            client_id="my_client_id",
            client_secret="my_client_secret")
