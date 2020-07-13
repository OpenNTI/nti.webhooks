===============
 Configuration
===============

``nti.webhooks`` uses :mod:`zope.configuration.xmlconfig` and ZCML files for
basic configuration.

Loading the default ``configure.zcml`` for this package establishes
some defaults, such as the default global :class:`webhook delivery
manager <nti.webhooks.interfaces.IWebhookDeliveryManager>`.

.. doctest::

   >>> from zope.configuration import xmlconfig
   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <include package="nti.webhooks" />
   ... </configure>
   ... """)

.. important::
   By itself, that is not enough for this package to be functional.

.. We link to the module because xrefs between projects for interfaces
   are broken as of July 2020.

The subscriber :func:`nti.webhooks.subscribers.dispatch_webhook_event`
must be registered as well, for some combination of data object and
(descendent of) :mod:`zope.interface.interfaces.IObjectEvent
<zope.interface.interfaces>`.

.. note:: Descending from ``IObjectEvent`` is not actually required,
          so long as the event provides the ``object`` attribute, and
          so long as double-dispatch from a single event to the double
          ``(object, event)`` subscriber interface happens. This is
          automatic for ``IObjectEvent``.

Because ``IObjectEvent`` and its descendents are extremely common
events, that subscriber is not registered by default. Doing so could
add unacceptable overhead to common application actions. It is
suggested that your application integration should register the
subscriber for a subset of "interesting" events and data types.

Your application integration is free to register the subscriber for
exactly the events that are desired. Or, to assist with common cases,
this package provides two additional ZCML files.

Recommended: ``subscribers.zcml``
=================================

This file registers the subscriber for commonly useful object
lifecycle events:

- :mod:`zope.lifecycleevent.interfaces.IObjectAddedEvent <zope.lifecycleevent.interfaces>`
- :mod:`zope.lifecycleevent.interfaces.IObjectModifiedEvent <zope.lifecycleevent.interfaces>`
- :mod:`zope.lifecycleevent.interfaces.IObjectRemovedEvent <zope.lifecycleevent.interfaces>`

.. note::

   The ``IObjectCreatedEvent`` is specifically *not* registered. While
   this is the first event typically sent during an object's
   lifecycle, when it is fired, the object is not required to have a
   location (``__name__`` and ``__parent__``) yet. It also typically
   does not have proper security constraints yet (which are usually
   location dependent). This means that URLs cannot be generated for
   it, nor can security be enforced.

Rather than register those for ``*``, meaning *any* object, those are
registered for
:class:`nti.webhooks.interfaces.IPossibleWebhookPayload`. This marker
interface is meant to be mixed in by the application to classes that
are subject to events and for which webhook delivery may be desired.

.. note::

   This is separate from
   :class:`nti.webhooks.interfaces.IWebhookPayload`, which is used as
   an adapter from an object delivered with an event to the object
   that should actually be externalized for delivery of the event.


For example:

.. doctest::

   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <include package="nti.webhooks" />
   ...   <include package="nti.webhooks" file="subscribers.zcml" />
   ...   <class class="nti.webhooks.testing.InterestingClass">
   ... 	    <implements interface="nti.webhooks.interfaces.IPossibleWebhookPayload" />
   ...   </class>
   ... </configure>
   ... """)


Development and Testing: ``subscribers_promiscuous.zcml``
=========================================================

This file registers the dispatcher for *all* object events for *all*
objects: ``(*, IObjectEvent*)``.

This may have performance consequences, so its use in production
systems is discouraged (unless the system is small). However, it is
extremely useful during development and (unit) testing and while
deciding which objects and events make useful webhooks.

Many of the tests and examples in the documentation for this package
use this file.

For example:

.. doctest::

   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <include package="nti.webhooks" />
   ...   <include package="nti.webhooks" file="subscribers_promiscuous.zcml" />
   ... </configure>
   ... """)

.. testcleanup::

   from zope.testing import cleanup
   cleanup.cleanUp()
