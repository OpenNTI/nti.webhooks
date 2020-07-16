
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

- Externalization
- Store some extra machine info on pending requests to help determine
  if they're still viable or should be redone.
- Store some exception info on failed requests (including those that
  don't pass the validator) for debugging purposes.

Dynamic-subscriptions only
--------------------------

- Removing subscriptions when principals are removed.
- Add dynamic subscription at higher level and find it too (we already
  have an example with static subscriptions). Maybe triggering on a
  different event type would be good too.
- Add test to add new subscription when manager already exists.
- API for deleting subscriptions.
- Auto-deactivate subscriptions after: not finding principals, number of failed deliveries, etc.
- Auto-copy principal from interaction when none is given.
- What about using nti.externalizations (?) "find primary interface"
  function as a generic ``IWebhookResourceDiscriminator``?
- Use the nti.zodb properties for the created/last modified time, as
  appropriate.


Thoughts on HTTP API
--------------------

- Generic end-point with context ``IPossibleWebhookPayload``; the last
  part of the path would be a shortcut name for the event.

====================
 Indices and tables
====================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
