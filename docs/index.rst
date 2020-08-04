
==============
 nti.webhooks
==============

.. contents::
   :local:

.. include:: ../README.rst
   :start-after: sphinx-include-begin-prelude
   :end-before: sphinx-include-after-prelude

.. note:: See the :doc:`glossary` for common terminology.

Documentation
=============

.. toctree::
   :maxdepth: 2

   scope
   glossary
   configuration
   static
   static-persistent
   security
   delivery_attempts
   subscription_security
   customizing_payloads
   dynamic
   events
   externalization
   api/index
   changelog



TODO
====

.. todo:: Write events document. Add specific events for subscription
          in/activated.
.. todo:: The concept of an active, in-process, retry policy.
.. todo:: An API to retry a failed request.
.. todo:: Add a dialect that uses a 'summary' externalizer. OR:
          Add a ZCML directive or argument that creates a dialect and
          specifies some common option names.

Dynamic-subscriptions only
--------------------------

.. todo::  Removing subscriptions when principals are removed.
.. todo::  API for deleting subscriptions. Probably done by finding
           all subscriptions for a resource/principal.
.. todo::  Auto-copy principal from interaction when none is given in api?
.. todo::  Use the nti.zodb properties for the created/last modified time, as
           appropriate.

Thoughts on HTTP API
--------------------

.. todo::  Generic end-point with context ``IPossibleWebhookPayload``; the last
           part of the path (or a query param?) would be a shortcut name for the event.
.. todo::  Getting the attempts for a subscription should be easy.
           Have an endpoint for the subscription, just externalize.

====================
 Indices and tables
====================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
