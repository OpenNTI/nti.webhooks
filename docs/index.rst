
==============
 nti.webhooks
==============

Contents:

.. toctree::
   :maxdepth: 1

   glossary
   configuration
   static
   security
   customizing_payloads
   delivery_attempts
   dynamic
   events
   api/index
   changelog


.. note:: See the :doc:`glossary` for common terminology.

.. include:: ../README.rst
   :start-after: sphinx-include-begin

TODO
====

.. todo:: Externalization
.. todo:: Write events document.

Dynamic-subscriptions only
--------------------------

.. todo::  Removing subscriptions when principals are removed.
.. todo::  Add dynamic subscription at higher level and find it too (we already
           have an example with static subscriptions). Maybe triggering on a
           different event type would be good too.
.. todo::  Add test to add new subscription when manager already exists.
.. todo::  API for deleting subscriptions.
.. todo::  Auto-deactivate subscriptions after: not finding principals, number of failed deliveries, etc.
.. todo::  Auto-copy principal from interaction when none is given.
.. todo::  What about using nti.externalizations (?) "find primary interface"
           function as a generic ``IWebhookResourceDiscriminator``?
.. todo::  Use the nti.zodb properties for the created/last modified time, as
           appropriate.

Thoughts on HTTP API
--------------------

.. todo::  Generic end-point with context ``IPossibleWebhookPayload``; the last
           part of the path would be a shortcut name for the event.

====================
 Indices and tables
====================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
