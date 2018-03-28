Quickstart
==========

.. py:module:: aio_sf_streaming

.. py:currentmodule:: aio_sf_streaming

Code organization
-----------------

*aio-sf-streaming* is designed in a modular way:

- :py:class:`BaseSalesforceStreaming` is the base class of the package. It
  implement the main logic of the streaming API flow. It is an abstract class,
  you can not use it directly, the class lake of connection capability. You
  must use one of the connector implementation.
- :ref:`connectors` add connection capabilities to
  :py:class:`BaseSalesforceStreaming` allowing to connect to Salesforce.
  :py:class:`PasswordSalesforceStreaming` allow to connect on Salesforce with 
  `password flow <https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/intro_understanding_username_password_oauth_flow.htm>`_.
  :py:class:`RefreshTokenSalesforceStreaming` allow to connect on Salesforce with 
  `refresh token flow <https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/intro_understanding_refresh_token_oauth.htm>`_.
- :ref:`mixins` are provided and can be added to concrete implementation to
  provide additional capabilities like `replay support <https://developer.salesforce.com/docs/atlas.en-us.api_streaming.meta/api_streaming/using_streaming_api_durability.htm>`_
  or use the provided timeout advice. This functionalities can be added
  by sub-classing a connector and add mixin to your concrete implementation.
- Helper class like :py:class:`SimpleSalesforceStreaming` simplify implementation
  with an "all-in-one" class implementation.

Asyncronous and Asyncio
-----------------------


Salesforce connection
---------------------

:py:class:`BaseSalesforceStreaming` allow you to connect with user name and
password of the user and client id and secret from the `connected app <https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/intro_defining_remote_access_applications.htm>`_.

Constructor does not establish any connection, you needs to call
:py:func:`BaseSalesforceStreaming.start` to connect to Salesforce and
start Bayeux/CometD protocol. Call ::py:func:`BaseSalesforceStreaming.stop` 
to disconnect and stop connection.

.. code-block:: python

    client = SimpleSalesforceStreaming(
                username='username',
                password='password',
                client_id='client_id',
                client_secret='client_secret')
    await client.start()
    # process events
    await client.stop()

Most of the time, you should not call theses methods directly, you should use
the asynchronous context manager interface that will call all of these for you:

.. code-block:: python

    async with SimpleSalesforceStreaming(
                    username='username',
                    password='password',
                    client_id='client_id',
                    client_secret='client_secret') as client:
        # process events

Subscribe to events
-------------------

Two methods :py:func:`BaseSalesforceStreaming.subscribe` and :py:func:`BaseSalesforceStreaming.unsubscribe` 
allow you to start receiving new events from a push topic or a generic streaming event
and stop when you does not want to receive event anymore.


.. code-block:: python

    async with SimpleSalesforceStreaming(**credentials) as client:
        # Subscribe to push topic
        await client.subscribe('/topic/Foo')
        # Subscribe to generic event
        await client.subscribe('/u/MyEvent')

        # Process events

        # Unsubscribe from push topic
        await client.unsubscribe('/topic/Foo')
        # Unsubscribe from generic event
        await client.unsubscribe('/u/MyEvent')

You can subscribe and unsubscribe at any moment and on other coroutine as
soon as the connection is established. You can even start to process without
waiting the response:

.. code-block:: python

    async def process(loop):
        async with SimpleSalesforceStreaming(**credentials, loop=loop) as client:
            loop.create_task(client.subscribe('/topic/Foo'))
            loop.create_task(client.subscribe('/topic/Bar'))

            # Process events

    loop = asyncio.get_event_loop()
    loop.run_until_complete(process(loop))

Receive events
--------------

:py:func:`BaseSalesforceStreaming.messages` and :py:func:`BaseSalesforceStreaming.events` 
are used to iterate over events when their are received. The main difference is
that :py:func:`BaseSalesforceStreaming.messages` provide all events, whereas
:py:func:`BaseSalesforceStreaming.events` filter internal messages and provide
only the events for channel you subscribed.

Both methods are asynchronous generator and should be iterate with `async for`:

.. code-block:: python

    async with SimpleSalesforceStreaming(**credentials) as client:
        await client.subscribe('/topic/Foo')
        await client.subscribe('/topic/Bar')

        async for event in client.events():
            channel = event['channel']
            print(f"Received an event from {channel} : {event}")


.. warning::
    Linked to the underlying protocol, long-pooling based, the client
    should reconnect as soon as possible. Practically, client have 40
    seconds to reconnect. If your processing take a longer time, a new
    connection should be made. You should avoid doing long processing
    between each iteration or launch this processing into a background
    task.

The processing loop is infinite by default. Inside the loop, you can stop
easily with a `break`:

.. code-block:: python

    async with SimpleSalesforceStreaming(**credentials) as client:
        await client.subscribe('/topic/Foo')
        await client.subscribe('/topic/Bar')

        async for event in client.events():
            channel = event['channel']
            if channel == '/topic/Foo':
                break
            else:
                print(event)

Outside the main loop, you can call :py:func:`BaseSalesforceStreaming.ask_stop`
to stop the loop as soon as is possible, even if your loop is waiting for a new
message. Please note that, due to the underlying protocol, this can take some
time to really happen (the code must wait a timeout from the server, can be as
long as 2min).

Replay support
--------------

:py:class:`ReplayMixin` add support of `24 hours events replay <https://developer.salesforce.com/docs/atlas.en-us.api_streaming.meta/api_streaming/using_streaming_api_durability.htm>`_.
Each event is associated with an unique id by channel. To support replay, you
must override two methods: :py:func:`ReplayMixin.store_replay_id` and :py:func:`ReplayMixin.get_last_replay_id`.

:py:func:`ReplayMixin.store_replay_id` is called for each received event. The
method is called with three arguments:

- the channel,
- the replay id,
- the object creation time.

For each channel, this function should store the replay id of the last created
object.

:py:func:`ReplayMixin.get_last_replay_id` will be called to retrieve the last
replay id for a specific channel. In addition of a specific id, this function
can return two special values from the :py:class:`ReplayType` enum to replay
all available events (24 hours history) or only new events after subscription.

The next example will store replay id in memory. In real world application you
should store this id in a persistent way:

.. code-block:: python

    class MyClient(SimpleSalesforceStreaming):
        def __init__(*args, **kwargs):
            self.replays = {}
            super().__init__(*args, **kwargs)

        async def store_replay_id(self, channel, replay_id, creation_time):
            # we does not want to store the replay id if a most recent one is
            # already stored
            last_storage = self.replays.get(channel, None)
            if last_storage and last_storage[0] > creation_time:
                return
            self.replays[channel] = (creation_time, replay_id)

        async def get_last_replay_id(self, channel):
            # Retrieve last replay
            last_storage = self.replays.get(channel, None)
            # If we have not any stored replay id, we can either replay all
            # events or only subscribe to new ones.
            if not last_storage:
                return ReplayType.NEW_EVENTS
            return last_storage[1]

