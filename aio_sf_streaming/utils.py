"""
Various utilities module
"""
import datetime
import re


def parse_sf_datetime(str_date: str) -> datetime.datetime:
    """
    Convert provided date from sf to datetime
    """
    # We can ignore remaining part
    pattern = (r'^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})'
               r'T(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})')
    values = re.match(pattern, str_date).groupdict()
    values = {key: int(value) for key, value in values.items()}
    return datetime.datetime(**values)
