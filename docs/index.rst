
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
   delivery_attempts
   subscription_security
   customizing_payloads
   dynamic
   events
   api/index
   changelog


.. note:: See the :doc:`glossary` for common terminology.

.. include:: ../README.rst
   :start-after: sphinx-include-begin

TODO
====

.. todo:: Externalization for the objects defined here.
          Note that we will need to be able to support the
          created/modified time properties as ISO format strings, not
          numbers for zapier.
.. todo:: Write events document.
.. todo:: Implement IDCTimes in terms of the native object
          properties. There's a helper function for this.

Dynamic-subscriptions only
--------------------------

.. todo::  Removing subscriptions when principals are removed.
.. todo::  Add dynamic subscription at higher level and find it too (we already
           have an example with static subscriptions). Maybe triggering on a
           different event type would be good too.
.. todo::  Add test to add new subscription when manager already exists.
.. todo::  API for deleting subscriptions. Probably done by finding
           all subscriptions for a resource/principal.
.. todo::  Auto-deactivate subscriptions after: applicability failures
           (e.g., not finding principals)
.. todo::  Auto-copy principal from interaction when none is given in api?
.. todo::  What about using nti.externalizations (?) "find primary interface"
           function as a generic ``IWebhookResourceDiscriminator``?
.. todo::  Use the nti.zodb properties for the created/last modified time, as
           appropriate.

Thoughts on HTTP API
--------------------

.. todo::  Generic end-point with context ``IPossibleWebhookPayload``; the last
           part of the path (or a query param?) would be a shortcut name for the event.

====================
 Indices and tables
====================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
