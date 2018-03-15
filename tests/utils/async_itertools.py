"""
Misc utils that reproduce iterating tool for coroutine
"""


async def async_enumerate(aiteror, start=0):
    """
    Simple enumerate
    """
    i = start
    async for value in aiteror:
        yield i, value
        i += 1
