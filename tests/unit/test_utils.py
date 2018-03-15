"""
Test utils functions
"""

import datetime
from aio_sf_streaming import parse_sf_datetime


def test_parse_sf_datetime():
    """
    test parse_sf_datetime function
    """

    assert (parse_sf_datetime("2018-03-01T12:00:42.123Z") ==
            datetime.datetime(2018, 3, 1, 12, 0, 42))

    assert (parse_sf_datetime("2018-03-01T12:00:42.123456Z") ==
            datetime.datetime(2018, 3, 1, 12, 0, 42))

    assert (parse_sf_datetime("2018-03-01T12:00:42") ==
            datetime.datetime(2018, 3, 1, 12, 0, 42))
