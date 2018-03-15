"""
Connectors module: Provide authentication implementation
"""

import logging

import aiohttp

from .core import BaseSalesforceStreaming

logger = logging.getLogger('aio_sf_streaming')


class PasswordSalesforceStreaming(BaseSalesforceStreaming):
    """
    Salesforce streaming client with password connection flow
    """

    def __init__(self, username, password, client_id, client_secret, *,
                 login_connector=None, **kwargs):
        """
        Create a SF streaming manager with password flow connection.

        Main arguments are connection credentials:

        :param username: User login name
        :param password: User password
        :param client_id: OAuth2 client Id
        :param client_secret: Oauth2 client secret

        :param login_connector: aiohttp connector used during connection. Used
        for test purpose.

        See :class:`.BaseSalesforceStreaming` for other keywords arguments.
        """
        if any(v is None for v in (username, password,
                                   client_id, client_secret)):
            raise TypeError("All credentials arguments are mandatory")

        self.login_connector = login_connector
        # Credentials used to fetch access token
        self.credentials = {
            'grant_type': 'password',
            'username': username,
            'password': password,
            'client_id': client_id,
            'client_secret': client_secret
        }
        super().__init__(**kwargs)

    async def fetch_token(self):
        # use a temporary session only to fetch token because client session
        # does not seems to allow update default headers on a already created
        # session
        async with aiohttp.ClientSession(connector=self.login_connector,
                                         headers=self.base_header,
                                         loop=self.loop) as session:
            async with session.post(self.token_url,
                                    data=self.credentials) as resp:
                data = await resp.json()

        assert data['token_type'] == 'Bearer'
        instance_url = data['instance_url']
        access_token = data['access_token']

        return access_token, instance_url
