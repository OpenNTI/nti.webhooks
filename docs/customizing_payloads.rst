===========================
 Customizing HTTP Requests
===========================

.. testsetup::

   from zope.testing import cleanup
   from nti.webhooks.testing import UsingMocks
   using_mocks = UsingMocks("POST", 'https://example.com/some/path', status=200)


Once an :term:`active` subscription matches and is :term:`applicable`
for a certain combination of object and event, eventually it's time to
create the actual HTTP request (body and headers) that will be
delivered to the target URL.

This document will outline how that is done, and discuss how to
customize that process. It will use :doc:`static subscriptions
<static>` to demonstrate, but these techniques are equally relevant
for :doc:`dynamic subscriptions <dynamic>`.

Let's begin by registering our example static subscription, and
refresh our memory of what the HTTP request looks like by default.
First, the imports and creation of the static subscription.

.. doctest::

   >>> import transaction
   >>> from zope import lifecycleevent, component
   >>> from zope.container.folder import Folder
   >>> from zope.configuration import xmlconfig
   >>> from nti.webhooks.interfaces import IWebhookSubscriptionManager
   >>> from nti.webhooks.interfaces import IWebhookDeliveryManager
   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <include package="zope.component" />
   ...   <include package="zope.container" />
   ...   <include package="nti.webhooks" />
   ...   <webhooks:staticSubscription
   ...             to="https://example.com/some/path"
   ...             for="zope.container.interfaces.IContentContainer"
   ...             when="zope.lifecycleevent.interfaces.IObjectCreatedEvent" />
   ... </configure>
   ... """)

Next, we :term:`trigger` the subscription and wait for it to be delivered.

.. doctest::

   >>> def trigger_delivery(factory=Folder, contents=()):
   ...    _ = transaction.begin()
   ...    folder = factory()
   ...    for k, v in contents: folder[k] = v
   ...    lifecycleevent.created(folder)
   ...    transaction.commit()
   ...    component.getUtility(IWebhookDeliveryManager).waitForPendingDeliveries()
   >>> trigger_delivery()

Finally, we can look at what we actually sent. It's not too pretty.

.. doctest::

   >>> sub_manager = component.getUtility(IWebhookSubscriptionManager)
   >>> subscription = sub_manager['Subscription']
   >>> attempt = subscription.pop()
   >>> attempt.response.status_code
   200
   >>> print(attempt.request.url)
   https://example.com/some/path
   >>> print(attempt.request.method)
   POST
   >>> import pprint
   >>> pprint.pprint({str(k): str(v) for k, v in attempt.request.headers.items()})
   {'Accept': '*/*',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Content-Length': '94',
    'Content-Type': 'application/json',
    'User-Agent': 'nti.webhooks...'}
   >>> print(attempt.request.body)
   {"Class": "NonExternalizableObject", "InternalType": "<class 'zope.container.folder.Folder'>"}


Customizing The Body
====================

There are a few different ways to customize the body, and they can be
applied at the same time.

The first way to customize the body is to register an adapter
producing an :class:`~nti.webhooks.interfaces.IWebhookPayload`. The
adapter can be an adapter for just the object, or it can be a
multi-adapter from the object and the event that triggered the
subscription. By default, both an adapter named
:attr:`.DefaultWebhookDialect.externalizer_name` and the unnamed
adapter are attempted. When such an adapter is found, its value is
externalized instead of the target of the event.

.. note::

   While a single adapter is frequently enough, multi-adapters are allowed
   in case the context of the event matters. For example, one might wish to
   externalize something different when an object is created versus when it is
   modified or deleted.

.. important::

   The security checks described in :doc:`security` apply to the object of the
   triggering event, *not* the adapted value.

Single Adapters
---------------

Working from lowest priority to highest priority, let's demonstrate some adapters.

First, an adapter for a single object with no name.

.. doctest::

   >>> from zope.interface import implementer
   >>> from zope.component import adapter
   >>> from nti.webhooks.interfaces import IWebhookPayload
   >>> @implementer(IWebhookPayload)
   ... @adapter(Folder)
   ... def single_adapter(folder):
   ...    return len(folder)
   >>> component.provideAdapter(single_adapter)

Triggering the event now produces a different body.

.. doctest::

   >>> trigger_delivery()
   >>> attempt = subscription.pop()
   >>> print(attempt.request.body)
   0
   >>> trigger_delivery(contents=[('k', 'v')])
   >>> attempt = subscription.pop()
   >>> print(attempt.request.body)
   1

Higher priority is a named adapter.

.. doctest::

   >>> from zope.component import named
   >>> @implementer(IWebhookPayload)
   ... @adapter(Folder)
   ... @named("webhook-delivery")
   ... def named_single_adapter(folder):
   ...     return "A folder"
   >>> component.provideAdapter(named_single_adapter)
   >>> trigger_delivery()
   >>> attempt = subscription.pop()
   >>> print(attempt.request.body)
   "A folder"

Of course, if the object already provides ``IWebhookPayload``,
then it is returned directly without using those adapters.

.. doctest::

   >>> @implementer(IWebhookPayload)
   ... class PayloadFactory(Folder):
   ...    """A folder that is its own payload."""
   >>> trigger_delivery(factory=PayloadFactory)
   >>> attempt = subscription.pop()
   >>> print(attempt.request.body)
   {"Class": "NonExternalizableObject", "InternalType": "<class 'PayloadFactory'>"}

Multi-adapters
--------------

Multi-adapters are the highest priority. They take precedence over the object itself
being a ``IWebhookPayload`` already.

The unnamed adapter for the event and the object is higher priority than the named single
adapter or the object itself.

.. doctest::

   >>> from zope.lifecycleevent.interfaces import IObjectCreatedEvent
   >>> @implementer(IWebhookPayload)
   ... @adapter(Folder, IObjectCreatedEvent)
   ... def multi_adapter(folder, event):
   ...    return "folder-and-event"
   >>> component.provideAdapter(multi_adapter)
   >>> trigger_delivery()
   >>> attempt = subscription.pop()
   >>> print(attempt.request.body)
   "folder-and-event"

Finally, the highest priority is a named multi-adapter.

.. doctest::

   >>> from zope.lifecycleevent.interfaces import IObjectCreatedEvent
   >>> @implementer(IWebhookPayload)
   ... @adapter(Folder, IObjectCreatedEvent)
   ... @named("webhook-delivery")
   ... def named_multi_adapter(folder, event):
   ...    return "named-folder-and-event"
   >>> component.provideAdapter(named_multi_adapter)
   >>> trigger_delivery()
   >>> attempt = subscription.pop()
   >>> print(attempt.request.body)
   "named-folder-and-event"


Cleanup
-------

Let's remove all those adapters and get back to a base state.

.. doctest::

   >>> gsm = component.getGlobalSiteManager()
   >>> gsm.unregisterAdapter(named_multi_adapter, name=named_multi_adapter.__component_name__)
   True
   >>> gsm.unregisterAdapter(multi_adapter)
   True
   >>> gsm.unregisterAdapter(named_single_adapter, name=named_single_adapter.__component_name__)
   True
   >>> gsm.unregisterAdapter(single_adapter)
   True

Webhook Dialects
================

Another way to customize the body, and much more, is to write a
:term:`dialect`. Every subscription is associated, by name, with a
dialect. Dialects are registered utilities that implement
:class:`nti.webhooks.interfaces.IWebhookDialect`; there is a global
default (the empty name, '') dialect implemented in
:class:`.DefaultWebhookDialect`. When defining new dialects, you
should extend this class. In fact, the behaviour defined above is
implemented by this class in its
:meth:`.DefaultWebhookDialect.produce_payload` method.

.. important::

   Dialects should not be persistent objects. They may be used outside
   of contexts where ZODB is available.


Setting the Body
----------------

One easy way to customize the body is to use named externalizers. The
default dialect uses an externalizer with the name given in
:attr:`~.DefaultWebhookDialect.externalizer_name`; a subclass can
change this by setting it on the class object. We'll demonstrate by
first defining and registering a
:class:`nti.externalization.interfaces.IInternalObjectExternalizer` with a custom name.

.. doctest::

   >>> from nti.externalization.interfaces import IInternalObjectExternalizer
   >>> @implementer(IInternalObjectExternalizer)
   ... @adapter(Folder)
   ... @named('webhook-testing')
   ... class FolderExternalizer(object):
   ...     def __init__(self, context):
   ...         self.context = context
   ...     def toExternalObject(self, **kwargs):
   ...         return {'Class': 'Folder', 'Length': len(self.context)}
   >>> component.provideAdapter(FolderExternalizer)

Next, we'll create a dialect that uses this externalizer, and register it:

.. doctest::

   >>> from nti.webhooks.dialect import DefaultWebhookDialect
   >>> @named('webhook-testing')
   ... class TestDialect(DefaultWebhookDialect):
   ...     externalizer_name = 'webhook-testing'
   >>> component.provideUtility(TestDialect())

We then alter the subscription to use this dialect:

.. doctest::

   >>> subscription.dialect_id = 'webhook-testing'

Now when we trigger the subscription, we use this externalizer:

.. doctest::

   >>> trigger_delivery()
   >>> attempt = subscription.pop()
   >>> print(attempt.request.body)
   {"Class": "Folder", "Length": 0}


Setting Headers
---------------

The dialect is also responsible for customizing aspects of the HTTP request,
including headers, authentication, and the method. Our previous attempt used the
default values for these things:

.. doctest::

   >>> print(attempt.request.method)
   POST
   >>> import pprint
   >>> pprint.pprint({str(k): str(v) for k, v in attempt.request.headers.items()})
   {'Accept': '*/*',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Content-Length': '32',
    'Content-Type': 'application/json',
    'User-Agent': 'nti.webhooks ...'}

Lets apply some simple customizations and send again.

.. doctest::
   :hide:

   >>> using_mocks.add('PUT', 'https://example.com/some/path')

.. doctest::

   >>> TestDialect.http_method = 'PUT'
   >>> TestDialect.user_agent = 'doctests'
   >>> trigger_delivery()
   >>> attempt = subscription.pop()
   >>> print(attempt.request.method)
   PUT
   >>> pprint.pprint({str(k): str(v) for k, v in attempt.request.headers.items()})
   {'Accept': '*/*',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Content-Length': '32',
    'Content-Type': 'application/json',
    'User-Agent': 'doctests'}



.. testcleanup::

   cleanup.addCleanUp(using_mocks.finish)
   from zope.testing import cleanup
   cleanup.cleanUp()
