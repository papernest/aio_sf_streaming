Introduction
============

*aio-sf-streaming* is a simple client library allowing  to connect to the
`Force.com Streaming API <https://developer.salesforce.com/docs/atlas.en-us.api_streaming.meta/api_streaming/intro_stream.htm>`_
and receive push event from Salesforce.

Salesforce can push two kind of events:

- `PushTopics <https://developer.salesforce.com/docs/atlas.en-us.api_streaming.meta/api_streaming/working_with_pushtopics.htm>`_
  allow you to monitor object and receive notification when the provided SOQL
  query match after an object creation, update or deletion.
- `Generic streaming <https://developer.salesforce.com/docs/atlas.en-us.api_streaming.meta/api_streaming/generic_streaming_intro.htm#generic_streaming_intro>`_
  allow to create custom events not linked to Saleforce object. Apex or API call
  allow you to trigger the event and receive notification in your streaming
  client.

*aio-sf-streaming* allow you to connect to Salesforce, subscribe for some events
and receive event when a change in a ``PushTopics`` is detected or when a generic
streaming event is trigged.

License
-------

*aio-sf-streaming* was created at `papernest <https://www.papernest.com>`_ and
is distribued under the MIT license.

------------------

.. include:: ../../LICENSE

