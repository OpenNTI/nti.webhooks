==============================
 Static Webhook Subscriptions
==============================

.. currentmodule:: nti.webhooks.zcml

The simplest type of webhook :term:`subscription` is one that is
configured statically, typically at application startup time. This
package provides ZCML directives to facilitate this. The directives
can either be used globally, creating subscriptions that are valid
across the entire application, or can be scoped to a smaller portion
of the application using `z3c.baseregistry`_.

.. autointerface:: IStaticSubscriptionDirective


Let's look at an example of how to use this directive from ZCML. We
need to define the XML namespace it's in, and we need to include the
configuration file that defines it. We also need to have the event
dispatching provided by :mod:`zope.component` properly set up, as well
as some other things. Including this package's configuration handles
all of that.

.. doctest::

   >>> from zope.configuration import xmlconfig
   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <include package="nti.webhooks" />
   ... </configure>
   ... """, execute=False)

Once that's done, we can use the ``webhooks:staticSubscription`` XML
tag to define a subscription to start receiving our webhook
deliveries.

There is only one required argument: the destination URL.

The destination must be HTTPS.

.. doctest::

   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <webhooks:staticSubscription to="http://example.com" />
   ... </configure>
   ... """, conf_context)
   Traceback (most recent call last):
   ...
   zope.configuration.exceptions.ConfigurationError: Invalid value for 'to'
       File "<string>", line 6.2-6.57
       zope.schema.interfaces.InvalidURI: http://example.com

If we specify a permission to check, it must exist.

.. doctest::

   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <webhooks:staticSubscription
   ...             to="https://example.com"
   ...             permission="no.such.permission" />
   ... </configure>
   ... """, conf_context)
   Traceback (most recent call last):
   ...
   zope.configuration.config.ConfigurationExecutionError: File "<string>", line 6.2-8.46
     Could not read source.
       ValueError: ('Undefined permission ID', 'no.such.permission')

.. doctest::
   :hide:

   >>> from zope.testing import cleanup
   >>> cleanup.cleanUp()


The above (unsuccessful) registration would have tried to send *all*
``IObjectEvent`` events for all objects that implement
:class:`~nti.webhooks.interfaces.IWebhookPayload` to
``https://example.com`` using the default dialect. That's unlikely to
be what you want, outside of tests. Instead, you'll want to limit the
event to particular kinds of objects, and particular events in their
lifecycle. The ``for`` and ``when`` attributes let you do that. Here,
we'll give a comple example saying that whenever a new
:mod:`IContainer <zope.container.interfaces>` is created, we'd like to
deliver a webhook.

.. doctest::

   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <include package="zope.component" />
   ...   <include package="zope.container" />
   ...   <include package="nti.webhooks" />
   ...   <webhooks:staticSubscription
   ...             to="https://this_domain_does_not_exist"
   ...             for="zope.container.interfaces.IContentContainer"
   ...             when="zope.lifecycleevent.interfaces.IObjectCreatedEvent" />
   ... </configure>
   ... """)

Now that we have that in place, let's verify that it exists:

.. doctest::

   >>> from nti.webhooks.interfaces import IWebhookSubscriptionManager
   >>> from zope import component
   >>> sub_manager = component.getUtility(IWebhookSubscriptionManager)
   >>> len(list(sub_manager))
   1
   >>> items = list(sub_manager.items())
   >>> print(items[0][0])
   Subscription
   >>> items[0][1]
   <...Subscription ... to='https://this_domain_does_not_exist' for=IContentContainer when=IObjectCreatedEvent>

And we'll verify that it is :term:`active`, by looking for it using
the event we just declared:

.. doctest::

   >>> from nti.webhooks.subscribers import find_active_subscriptions_for
   >>> from zope.container.folder import Folder
   >>> from zope.lifecycleevent import ObjectCreatedEvent
   >>> event = ObjectCreatedEvent(Folder())
   >>> len(find_active_subscriptions_for(event.object, event))
   1
   >>> find_active_subscriptions_for(event.object, event)
   [<...Subscription ... to='https://this_domain_does_not_exist' for=IContentContainer when=IObjectCreatedEvent>]


Next, we need to know if the subscription is :term:`applicable` to the
data. Since we didn't specify a permission or a principal to check, the subscription is applicable:

.. doctest::

   >>> subscriptions = find_active_subscriptions_for(event.object, event)
   >>> [subscription.isApplicable(event.object) for subscription in subscriptions]
   [True]

Now lets demonstrate what happens when we actually fire this event. First, we must be in a transaction:

.. doctest::

   >>> import transaction
   >>> tx = transaction.begin()

Fire the event:

.. doctest::

   >>> from zope import lifecycleevent
   >>> lifecycleevent.created(Folder())

We can see that we have attached a data manager to the transaction:

.. doctest::

   >>> tx._resources
   [<nti.webhooks.datamanager.WebhookDataManager...>]

However, recall that we specified an invalid domain name, so there is
no where to attempt to deliver the webhook too. For static webhooks,
this is generally a deployment configuration problem and should be
attended to by correcting the ZCML. For dynamic subscriptions, the
error would be corrected by updating the subscription. This doesn't fail the commit:

.. doctest::

   >>> transaction.commit()

But it does record a failed attempt in the subscription:

.. doctest::

   >>> subscription = sub_manager['Subscription']
   >>> len(subscription)
   1
   >>> attempt = list(subscription.values())[0]
   >>> attempt.status
   'failed'
   >>> print(attempt.message)
   Verification of the destination URL failed. Please check the domain.



Let's reset things and look at what a successful delivery might look like.

.. doctest::

   >>> from zope.testing import cleanup
   >>> cleanup.cleanUp()
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
   >>> subscription = sub_manager['Subscription']
   >>> len(subscription)
   0

As before, we configure the package (this time with a resolvable URL)
and get the subscription object, confirming that it has no history. To
avoid actually trying to talk to example.com, we'll install some mocks
(this will be hidden from the rendered documentation because it's an
implementation detail).

.. doctest::
   :hide:

   >>> import responses
   >>> import contextlib
   >>> @contextlib.contextmanager
   ... def using_mocks():
   ...   with responses.RequestsMock() as mock:
   ...       mock.add(responses.POST, 'https://example.com/some/path', status=200)
   ...       yield
   >>> mock_network = using_mocks()
   >>> mock_network.__enter__()

Now we will create the object and send the hook.

.. doctest::

   >>> _ = transaction.begin()
   >>> lifecycleevent.created(Folder())
   >>> transaction.commit()

In the background, the ``IWebhookDeliveryManager`` is busy invoking the hook. We need to wait for it to
finish, and then we can examine our delivery attempt:

.. doctest::

   >>> from zope import component
   >>> from nti.webhooks.interfaces import IWebhookDeliveryManager
   >>> component.getUtility(IWebhookDeliveryManager).waitForPendingDeliveries()

.. doctest::
   :hide:

   >>> _ = mock_network.__exit__(None, None, None)

.. doctest::

   >>> len(subscription)
   1
   >>> attempt = list(subscription.values())[0]
   >>> attempt.status
   'successful'
   >>> print(attempt.message)
   200 OK


.. _z3c.baseregistry: https://github.com/zopefoundation/z3c.baseregistry/tree/master/src/z3c/baseregistry


.. testcleanup::

   from zope.testing import cleanup
   cleanup.cleanUp()
