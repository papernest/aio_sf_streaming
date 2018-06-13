.. _api:

Developer Interface
===================

.. py:module:: aio_sf_streaming

.. py:currentmodule:: aio_sf_streaming

This part of the documentation covers all the interfaces of *aio_sf_streaming*.

Code organization
-----------------

The package is separated in 5 mains modules:

- High-level classes and helpers are provided to have a quickly functional
  client. See :ref:`main_interface` section.
- The :ref:`base_class` section describe the low-level base class that
  implement the main client logic.
- To authenticate on Salesforce, you must use one connector that add
  authentication capability to :py:class:`BaseSalesforceStreaming`. See
  :ref:`connectors` section for a list of available connectors.
- :ref:`mixins` extend :py:class:`BaseSalesforceStreaming` capabilities and
  can be added easily as opt-in option by sub classing.
- Finally, :ref:`utils` provide some internal utilities functions.


.. _main_interface:

Main Interface
--------------

.. autoclass:: SimpleSalesforceStreaming

   :py:class:`SimpleSalesforceStreaming` inherit all members from their base
   class. Only main one, for external use, are listed here.

   .. autocomethod:: start
   .. autocomethod:: subscribe
   .. autocomethod:: messages
      :async-for:
   .. autocomethod:: events
      :async-for:
   .. autocomethod:: store_replay_id
   .. autocomethod:: get_last_replay_id
   .. autocomethod:: ask_stop
   .. autocomethod:: unsubscribe
   .. autocomethod:: stop

.. autoclass:: SimpleRefreshTokenSalesforceStreaming

   :py:class:`SimpleSalesforceStreaming` inherit all members from their base
   class. Only main one, for external use, are listed here. See
   :py:class:`SimpleRefreshTokenSalesforceStreaming`  for method description.

.. _base_class:

Base class
----------

.. autoclass:: BaseSalesforceStreaming

   **High level api**

   .. autocomethod:: start
   .. autocomethod:: subscribe
   .. autocomethod:: messages
      :async-for:
   .. autocomethod:: events
      :async-for:
   .. autocomethod:: ask_stop
   .. autocomethod:: unsubscribe
   .. autocomethod:: stop

   **Connection logic**

   .. autoattribute:: token_url
   .. autocomethod:: fetch_token
   .. autocomethod:: create_connected_session
   .. autocomethod:: close_session

   **Bayeux/CometD logic layer**

   .. autoattribute:: end_point
   .. autocomethod:: get_handshake_payload
   .. autocomethod:: get_subscribe_payload
   .. autocomethod:: get_unsubscribe_payload
   .. autocomethod:: send
   .. autocomethod:: handshake
   .. autocomethod:: disconnect

   **I/O layer helpers**

   .. autocomethod:: get
   .. autocomethod:: post
   .. autocomethod:: request

   **Other attributes**

   .. autoattribute:: loop


.. _connectors:

Connectors
----------

.. autoclass:: BaseConnector

.. autoclass:: PasswordSalesforceStreaming

.. autoclass:: RefreshTokenSalesforceStreaming

.. _mixins:

Mixins
------

.. autoclass:: AllMixin

.. autoclass:: TimeoutAdviceMixin

.. autoclass:: ReplayType
   :members:

.. autoclass:: ReplayMixin
   :members: store_replay_id, get_last_replay_id

.. autoclass:: AutoVersionMixin

.. autoclass:: AutoReconnectMixin

.. autoclass:: ReSubscribeMixin


.. _utils:

