aio_sf_streaming
================

*aio_sf_streaming* is a simple Python 3.6 asyncio library allowing to connect
and receive live notifications from Salesforce. This library is provided to
you by `papernest <http://www.papernest.com>`_.

See `The Force.com streaming API developer guide <https://developer.salesforce.com/docs/atlas.en-us.api_streaming.meta/api_streaming/intro_stream.htm>`_
for more information about the different uses cases and how configure your
Salesforce organization.


Feature
-------

- `asyncio <https://docs.python.org/3/library/asyncio.html>`_ compatible library
- Subscribe to push topics and custom events
- Receive events pushed by Salesforce
- Auto-reconnect after too many time of inactivity
- Replay support: replay events missed while your client is disconnected (see 
  `Force.com documentation <https://developer.salesforce.com/docs/atlas.en-us.api_streaming.meta/api_streaming/using_streaming_api_stateless.htm>`_
  for more information).

*aio_sf_streaming* only support Python 3.6 for now.


Getting started
---------------

Simple use case:

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
            async for message in client.events():
                print(message)
                # client will wait indefinitely, you can ask to exit
                if message['channel'] == '/topic/Bar':
                    await client.ask_stop()
                else:
                    # You can unsubscribe when you want, too
                    await client.unsubscribe('/topic/Foo')
  
    loop = asyncio.get_event_loop()
    loop.run_until_complete(print_event())


Installation
------------

Simply use ``pip``:

.. code-block:: bash

    $ pip install aio_sf_streaming


Documentation
-------------

A online documentation is available at .


Evolution
---------

The library work well for our use-case then we does not plan a lot of new 
features. The only planned feature is the addition of the OAuth2 browser flow
`refresh_token` for authentication instead of user name and passwords.


Release history
---------------

**v. 0.1**: Initial release


License
=======

``aio_sf_streaming`` is offered under the MIT license.

