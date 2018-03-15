"""
aio_sf_streaming
~~~~~~~~~~~~~~~~

aio_sf_streaming is a simple asyncio Salesforce Streaming API client for
Python 3.6+
"""
from .core import BaseSalesforceStreaming
from .connectors import PasswordSalesforceStreaming
from .mixins import (TimeoutAdviceMixin, AutoVersionMixin, ReplayMixin,
                     ReplayType, AutoReconnectMixin, ReSubscribeMixin)
from .utils import parse_sf_datetime


class AllMixin(
        TimeoutAdviceMixin,             # Use SF timeout advice
        AutoVersionMixin,               # Auto-fetch last api version
        ReplayMixin,                    # Add replay support
        AutoReconnectMixin,             # Add auto-reconnection feature
        ReSubscribeMixin):              # Handle subscription errors
    """
    Helper class to add all mixin with one class
    """


class SimpleSalesforceStreaming(
        AllMixin,
        PasswordSalesforceStreaming):   # Password flow
    """
    A simple helper class providing all-in-one functionalities
    """
