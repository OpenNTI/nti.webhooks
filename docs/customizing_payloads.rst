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

   >>> def trigger_delivery(contents=()):
   ...    _ = transaction.begin()
   ...    folder = Folder()
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
    'User-Agent': '...'}
   >>> print(attempt.request.body)
   {"Class": "NonExternalizableObject", "InternalType": "<class 'zope.container.folder.Folder'>"}


Customizing The Body
====================

There are a few different ways to customize the body, and they can be
applied at the same time.

The first way to customize the body is to register an adapter
producing an ``IWebhookPayload.`` The adapter can be an adapter for
just the object, or it can be a multi-adapter from the object and the
event that triggered the subscription. By default, both an adapter
named :attr:`.DefaultWebhookDialect.externalizer_name` and the unnamed
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

Working from lowest priority to highest priority, let's demonstrate some adapters.

First, an adapter for a single object with no name.

.. doctest::

   >>> from zope.interface import implementer
   >>> from zope.component import adapter
   >>> from nti.webhooks.interfaces import IWebhookPayload
   >>> @implementer(IWebhookPayload)
   ... @adapter(Folder)
   ... def trivial_adapter(folder):
   ...    return len(folder)
   >>> component.provideAdapter(trivial_adapter)

Triggering the event now produces a different body.

.. doctest::

   >>> trigger_delivery()
   >>> attempt = subscription.pop()
   >>> print(attempt.request.body)
   0
   >>> trigger_delivery([('k', 'v')])
   >>> attempt = subscription.pop()
   >>> print(attempt.request.body)
   1

Higher priority is a named adapter.

.. doctest::

   >>> from zope.component import named
   >>> @implementer(IWebhookPayload)
   ... @adapter(Folder)
   ... @named("webhook-delivery")
   ... def named_adapter(folder):
   ...     return "A folder"
   >>> component.provideAdapter(named_adapter)
   >>> trigger_delivery()
   >>> attempt = subscription.pop()
   >>> print(attempt.request.body)
   "A folder"

- Talk about writing dialects.
- Talk about adapting ``event.object`` to ``IWebhookPayload`` (and
  actually write that).


.. testcleanup::

   cleanup.addCleanUp(using_mocks.finish)
   from zope.testing import cleanup
   cleanup.cleanUp()
