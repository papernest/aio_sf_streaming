"""
Various async utilities functions
"""
import asyncio


async def wait_until_all_completed():
    """
    Small utility that check pending tasks and return when theire is only one
    (= the active task)
    """
    pending = asyncio.Task.all_tasks()
    while "not all tasks completed":
        _, pending = await asyncio.wait(pending,
                                        return_when=asyncio.FIRST_COMPLETED)
        if len(pending) == 1:
            return
