.. aio-sf-streaming documentation master file, created by
   sphinx-quickstart on Fri Mar 16 09:23:22 2018.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to aio-sf-streaming's documentation!
============================================

.. image:: https://badge.fury.io/py/aio-sf-streaming.svg
    :target: https://badge.fury.io/py/aio-sf-streaming
    :alt: Last release

.. image:: https://travis-ci.org/papernest-public/aio_sf_streaming.svg?branch=master
    :target: https://travis-ci.org/papernest-public/aio_sf_streaming
    :alt: Build

.. image:: https://img.shields.io/badge/License-MIT-yellow.svg
    :target: https://opensource.org/licenses/MIT
    :alt: MIT license

*aio-sf-streaming* is a simple Python 3.6 asyncio library allowing to connect
and receive live notifications from Salesforce. This library is provided to
you by `papernest <http://www.papernest.com>`_.

See `The Force.com streaming API developer guide <https://developer.salesforce.com/docs/atlas.en-us.api_streaming.meta/api_streaming/intro_stream.htm>`_
for more information about the different uses cases and how configure your
Salesforce organization.

**Simple example**

.. code-block:: python

    import asyncio
    from aio_sf_streaming import SimpleSalesforceStreaming

    async def print_event():
        # Create client and connect
        async with SimpleSalesforceStreaming(
                        username='my-username',
                        password='my-password',
                        client_id='my-client-id',
                        client_secret='my-client-secret') as client:
            # Subscribe to some push topics
            await client.subscribe('/topic/Foo')
            await client.subscribe('/topic/Bar')
            # Print received message infinitely
            async for message in client.events():
                channel = message['channel']
                print(f"Message received on {channel} : {message}")
  
    loop = asyncio.get_event_loop()
    loop.run_until_complete(print_event())


**Main features**

- `asyncio <https://docs.python.org/3/library/asyncio.html>`_ compatible library
- Subscribe to push topics and custom events
- Receive events pushed by Salesforce
- Auto-reconnect after too many time of inactivity
- Replay support: replay events missed while your client is disconnected (see 
  `Force.com documentation <https://developer.salesforce.com/docs/atlas.en-us.api_streaming.meta/api_streaming/using_streaming_api_stateless.htm>`_
  for more information).

*aio-sf-streaming* only support Python 3.6 for now.

User Guide
----------

.. toctree::
   :maxdepth: 2

   user/intro


Reference Documentation
-----------------------

.. toctree::
   :maxdepth: 2

   api
