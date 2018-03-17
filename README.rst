aio-sf-streaming
================

.. image:: https://badge.fury.io/py/aio-sf-streaming.svg
    :target: https://badge.fury.io/py/aio-sf-streaming
    :alt: Last release

.. image:: https://readthedocs.org/projects/aio-sf-streaming/badge/?version=latest
    :target: http://aio-sf-streaming.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

.. image:: https://travis-ci.org/papernest-public/aio_sf_streaming.svg?branch=master
    :target: https://travis-ci.org/papernest-public/aio_sf_streaming
    :alt: Build

.. image:: https://coveralls.io/repos/github/papernest-public/aio_sf_streaming/badge.svg
    :target: https://coveralls.io/github/papernest-public/aio_sf_streaming
    :alt: Coverage

.. image:: https://api.codeclimate.com/v1/badges/e0c891514893bdd4c22f/maintainability
   :target: https://codeclimate.com/github/papernest-public/aio_sf_streaming/maintainability
   :alt: Maintainability

.. image:: https://requires.io/github/papernest-public/aio_sf_streaming/requirements.svg?branch=master
    :target: https://requires.io/github/papernest-public/aio_sf_streaming/requirements/?branch=master
    :alt: Requirements Status

.. image:: https://img.shields.io/badge/License-MIT-yellow.svg
    :target: https://opensource.org/licenses/MIT
    :alt: MIT license

*aio-sf-streaming* is a simple Python 3.6 asyncio library allowing to connect
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

*aio-sf-streaming* only support Python 3.6 for now.


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
                    break
                else:
                    # You can unsubscribe when you want, too
                    await client.unsubscribe('/topic/Foo')
  
    loop = asyncio.get_event_loop()
    loop.run_until_complete(print_event())


Installation
------------

Simply use ``pip``:

.. code-block:: bash

    $ pip install aio-sf-streaming


Documentation
-------------

A online documentation is available at .


Evolution
---------

The library work well for our use-case then we does not plan a lot of new 
features. The only planned feature is the addition of the OAuth2 browser flow
`refresh_token` for authentication instead of user name and passwords.


Contributing
------------

If you find any problem, feel free to fill an issue. Pull-Request are also
welcomed.

You can install development dependencies with:

.. code-block:: bash

    $ pip install -e .[tests,docs]

Release history
---------------

- **v. 0.1.1**: Add documentation and initial typing information.
- **v. 0.1.0**: Initial release.


License
=======

``aio-sf-streaming`` is offered under the MIT license.

