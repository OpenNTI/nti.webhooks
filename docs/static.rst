====================================================
 Configured Global, Transient Webhook Subscriptions
====================================================

.. currentmodule:: nti.webhooks.zcml

.. testsetup::

   from zope.testing import cleanup


The simplest type of webhook :term:`subscription` is one that is
configured statically, typically at application startup time, and
stores no persistent history (with the facilities provided by this
package; applications may store their own history, perhaps by
listening for :doc:`delivery events <events>`).

This is useful for a number of scenarios, including:

- Development;
- Integration testing;
- Fire-and-forget delivery of frequent events;
- Simple applications.

This package provides ZCML directives to facilitate this. The
directives can either be used globally, creating subscriptions that
are valid across the entire application.

.. autointerface:: IStaticSubscriptionDirective


Let's look at an example of how to use this directive from ZCML. We
need to define the XML namespace it's in, and we need to include the
configuration file that defines it. We also need to have the event
dispatching provided by :mod:`zope.component` properly set up, as well
as some other things described in :doc:`configuration`. Including this
package's configuration handles all of that.

.. doctest::

   >>> from zope.configuration import xmlconfig
   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <include package="nti.webhooks" />
   ...   <include package="nti.webhooks" file="subscribers_promiscuous.zcml" />
   ... </configure>
   ... """, execute=False)

Once that's done, we can use the ``webhooks:staticSubscription`` XML
tag to define a subscription to start receiving our webhook
deliveries.

ZCML Directive Arguments
========================

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

Specifying Which Objects
------------------------

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
   ...   <include package="nti.webhooks" file="subscribers_promiscuous.zcml" />
   ...   <webhooks:staticSubscription
   ...             to="https://this_domain_does_not_exist"
   ...             for="zope.container.interfaces.IContentContainer"
   ...             when="zope.lifecycleevent.interfaces.IObjectCreatedEvent" />
   ... </configure>
   ... """)

.. note::

   Sometimes, the ``for`` and ``when`` attributes may not quite get
   you what you want. You can use an adapter to
   :class:`nti.webhooks.interfaces.IWebhookPayload` to derive the desired data. For more, see
   :doc:`customizing_payloads`.

Active Subscriptions
====================

Now that we have that in place, let's verify that it exists as part of
the global default ``IWebhookSubscriptionManager``.

.. doctest::

   >>> from nti.webhooks.interfaces import IWebhookSubscriptionManager
   >>> from zope import component
   >>> sub_manager = component.getUtility(IWebhookSubscriptionManager)
   >>> from zope.interface import verify
   >>> verify.verifyObject(IWebhookSubscriptionManager, sub_manager)
   True
   >>> len(list(sub_manager))
   1
   >>> name, subscription = list(sub_manager.items())[0]
   >>> print(name)
   Subscription
   >>> subscription
   <...Subscription ... to='https://this_domain_does_not_exist' for=IContentContainer when=IObjectCreatedEvent>

And we'll verify that it is :term:`active`, by looking for it using
the event we just declared:

.. doctest::

   >>> from nti.webhooks.subscribers import find_active_subscriptions_for
   >>> from zope.container.folder import Folder
   >>> from zope.lifecycleevent import ObjectCreatedEvent
   >>> event = ObjectCreatedEvent(Folder())
   >>> active_subscriptions = list(find_active_subscriptions_for(event.object, event))
   >>> len(active_subscriptions)
   1
   >>> active_subscriptions[0]
   <...Subscription ... to='https://this_domain_does_not_exist' for=IContentContainer when=IObjectCreatedEvent>
   >>> active_subscriptions[0] is subscription
   True
   >>> subscription.active
   True

Next, we need to know if the subscription is :term:`applicable` to the
data. Since we didn't specify a permission or a principal to check, the subscription is applicable:

.. seealso:: :doc:`security` for information on security checks.

.. doctest::

   >>> subscriptions = find_active_subscriptions_for(event.object, event)
   >>> [subscription.isApplicable(event.object) for subscription in subscriptions]
   [True]

Delivery Attempts
=================

All attempts at delivering a webhook are recorded. Delivery always
occurs as a result of committing a transaction, and the resulting
attempt object is stored in the corresponding subscription object.

Here, we will briefly look at what happens when we attempt to deliver
this webhook. Recall that it uses a domain that does not exist.

.. seealso:: :doc:`delivery_attempts` for more on delivery attempts.
.. seealso:: :doc:`customizing_payloads` for information on
             customizing what is sent in the delivery attempt.

Unsuccessful Delivery Attempts
------------------------------

Because delivery is transactional, to begin we must be in a transaction:

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

Don't Fail The Transaction
~~~~~~~~~~~~~~~~~~~~~~~~~~

However, recall that we specified an invalid domain name, so there is
nowhere to attempt to deliver the webhook too. For static webhooks,
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
   >>> len(attempt.internal_info.exception_history)
   1
   >>> print(attempt.internal_info.exception_history[0])
   Traceback (most recent call last):
   ...


.. _z3c.baseregistry: https://github.com/zopefoundation/z3c.baseregistry/tree/master/src/z3c/baseregistry


Inactive Subscriptions
======================

.. XXX: This doesn't really belong here.

Subscriptions can be deactivated (made :term:`inactive`) by asking the
manager to do this. The subscription manager is always the subscription's parent,
and deactivating the subscription more than once does nothing.

.. doctest::

   >>> subscription.__parent__ is sub_manager
   True
   >>> sub_manager.deactivateSubscription(subscription)
   True
   >>> sub_manager.deactivateSubscription(subscription)
   False
   >>> subscription.active
   False

Note that we cannot change this attribute directly, it must be done through the manager.

.. doctest::

   >>> subscription.active = True
   Traceback (most recent call last):
   ...
   ValueError:...field is readonly

Inactive subscriptions will not be used for future deliveries, but
their existing history is preserved.

.. doctest::

   >>> len(subscription)
   1
   >>> find_active_subscriptions_for(event.object, event)
   []
   >>> tx = transaction.begin()
   >>> lifecycleevent.created(Folder())
   >>> tx._resources
   []
   >>> transaction.commit()
   >>> len(subscription)
   1

Of course, inactive subscriptions can be activated again.

.. doctest::

   >>> sub_manager.activateSubscription(subscription)
   True
   >>> subscription.active
   True
   >>> tx = transaction.begin()
   >>> lifecycleevent.created(Folder())
   >>> transaction.commit()
   >>> len(subscription)
   2

Removing a subscription from its subscription manager automatically deactivates
it.

.. doctest::

   >>> del sub_manager[subscription.__name__]
   >>> subscription.__parent__ is None
   True
   >>> subscription.active
   False

.. testcleanup::

   from zope.testing import cleanup
   cleanup.cleanUp()
