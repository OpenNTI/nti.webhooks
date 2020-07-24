=======================
 Subscription Security
=======================

In :doc:`security`, we covered the checks that are applied when
determining whether to deliver an event's object to a particular
:term:`subscription's <subscription>` :term:`target`.

This document will cover the security that's applied to the
subscriptions themselves.

Subscription security is based on :mod:`zope.securitypolicy`, using
its concepts of principals, roles, permissions, and granting or
denying permissions to principals or roles,

Each subscription that has an owner grants read (``zope.View``) and
delete (``nti.actions.delete``) access to that owner. No other
permissions are defined or used; any other access must be inherited
from the subscription's lineage. Typically this will mean that
principals with the role ``zope.Manager`` will have complete access;
if you load the ``securitypolicy.zcml`` configuration from
:mod:`zope.securitypolicy`, then anonymous users will :ref:`also have
access <default-view-access>`. If there is no owner, then no specific
grants will be made.

This applies equally for both static and dynamic subscriptions, and
can be customized; see :ref:`customizing_the_grants` for more
information.

Set Up
======

The following documentation will use the basic set up presented here.
We'll begin by loading the necessary ZCML configuration, including the
default Zope security policy (but we'll disable the anonymous access
for demonstration purposes).


.. doctest::

   >>> from zope.configuration import xmlconfig
   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <include package="zope.component" />
   ...   <include package="zope.container" />
   ...   <include package="zope.principalregistry" />
   ...   <include package="zope.securitypolicy" />
   ...   <!-- This defines permission nti.actions.delete and must be
   ...        before zope.securitypolicy:securitypolicy.zcml
   ...        for the zope.Manager role to be granted it. -->
   ...   <include package="nti.webhooks" />
   ...   <include package="zope.securitypolicy" file="securitypolicy.zcml" />
   ...   <include package="nti.webhooks" file="subscribers_promiscuous.zcml" />
   ...   <deny role="zope.Anonymous" permission="zope.View" />
   ... </configure>
   ... """)


Next, we'll define a few principals ('Alice' and 'Bob'), including
one ('Manager') that we grant the ``zope.Manager`` role to.

.. doctest::

   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <include package="zope.securitypolicy" file="meta.zcml" />
   ...   <include package="zope.principalregistry" file="meta.zcml" />
   ...   <principal
   ...         id="webhook.alice"
   ...         title="Alice"
   ...         login="alice"
   ...         password_manager="SHA1"
   ...         password="40bd001563085fc35165329ea1ff5c5ecbdbbeef"
   ...         />
   ...   <principal
   ...         id="webhook.bob"
   ...         title="Bob"
   ...         login="bob"
   ...         password_manager="SHA1"
   ...         password="40bd001563085fc35165329ea1ff5c5ecbdbbeef"
   ...         />
   ...   <principal
   ...         id="webhook.manager"
   ...         title="Manager"
   ...         login="manager"
   ...         password_manager="SHA1"
   ...         password="40bd001563085fc35165329ea1ff5c5ecbdbbeef"
   ...         />
   ...   <grant role="zope.Manager" principal="webhook.manager" />
   ... </configure>
   ... """)

Lastly, we'll define a subscription for Alice.

.. doctest::

   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <include package="nti.webhooks" />
   ...   <webhooks:staticSubscription
   ...             to="https://example.com/some/path"
   ...             for="zope.container.interfaces.IContentContainer"
   ...             when="zope.lifecycleevent.interfaces.IObjectCreatedEvent"
   ...             permission="zope.View"
   ...             owner="webhook.alice" />
   ... </configure>
   ... """)


Access To The Subscription
==========================

.. todo:: Write a subscriber and example for when the owner_id of a
          subscription changes. Currently that's forbidden by the
          docs.

We'll use a helper function to demonstrate access rights.

.. doctest::

   >>> from zope.security.testing import interaction
   >>> from zope.security import checkPermission
   >>> from collections import namedtuple
   >>> Permissions = namedtuple("Permissions",
   ...                          ('view', 'delete', 'other'))
   >>> def checkPermissions(principal_id, object):
   ...    def check(permission_id):
   ...        with interaction(principal_id):
   ...            return checkPermission(permission_id, object)
   ...    return Permissions(
   ...       check('zope.View'),
   ...       check('nti.actions.delete'),
   ...       check('zope.ManageContent'),
   ...    )

The Alice principal has view and delete access to the subscription.
We'll use a helper function to demonstrate this.

.. doctest::

   >>> from zope import component
   >>> from nti.webhooks import interfaces
   >>> sub_manager = component.getUtility(interfaces.IWebhookSubscriptionManager)
   >>> subscription = sub_manager['Subscription']
   >>> checkPermissions('webhook.alice', subscription)
   Permissions(view=True, delete=True, other=False)

The manager also has view and delete access, plus a bunch of other inherited things:

.. doctest::

   >>> checkPermissions('webhook.manager', subscription)
   Permissions(view=True, delete=True, other=True)

The other principal has no access:

.. doctest::

   >>> checkPermissions('webhook.bob', subscription)
   Permissions(view=False, delete=False, other=False)

Access to Delivery Attempts
===========================

The same access rights flow down to delivery attempts contained within
a subscription. A helper to fire the deliveries is already defined.

.. literalinclude:: delivery_helper.py

To avoid actually trying to talk to example.com, we'll be using some mocks.

.. doctest::

   >>> from nti.webhooks.testing import mock_delivery_to
   >>> mock_delivery_to('https://example.com/some/path', method='POST', status=200)

We'll perform the delivery as someone with high-privileges (the manager);
we have to perform the delivery as someone because we need to be able to check permissions
on the object.

.. doctest::

   >>> from delivery_helper import deliver_some, wait_for_deliveries
   >>> with interaction('webhook.manager'):
   ...     deliver_some(how_many=1, grants={'webhook.alice': 'zope.View'})
   >>> wait_for_deliveries()

Now we can check the access rights for the recorded delivery attempt.
All three principals should have the same access to the attempt that
they had to the subscription.

.. doctest::

   >>> attempt = subscription.pop()
   >>> checkPermissions('webhook.alice', attempt)
   Permissions(view=False, delete=False, other=False)
   >>> checkPermissions('webhook.manager', attempt)
   Permissions(view=True, delete=True, other=True)
   >>> checkPermissions('webhook.bob', attempt)
   Permissions(view=False, delete=False, other=False)

Wait, how come no one except the manager had any access? What happened
to Alice? When we popped the attempt out of the subscription, it lost
its ``__parent__`` and disconnected from the lineage and hence the
inherited flow of permissions. Let's put it back and check again.

.. doctest::

   >>> attempt.__parent__ is None
   True
   >>> subscription['attempt'] = attempt
   >>> checkPermissions('webhook.alice', attempt)
   Permissions(view=True, delete=True, other=False)
   >>> checkPermissions('webhook.manager', attempt)
   Permissions(view=True, delete=True, other=True)
   >>> checkPermissions('webhook.bob', attempt)
   Permissions(view=False, delete=False, other=False)


Security Proxies
================

The global subscription manager (used here) is *not* registered with
any permission. That means it does not have a security proxy wrapped
around it, and thus, any user could potentially trigger deliveries.
Likewise, the site-specific subscription managers (documented in
:doc:`dynamic`) also do not have security proxies created for them.

Traversal, however, is free to create security proxies. If you're not
using security proxies, then take the appropriate care to honor these
permissions. For example, Pyramid view registrations should use these
permissions before allowing access.

.. _customizing_the_grants:

Customizing The Permission Grants
=================================

For information on customizing the permission grants, see
:func:`nti.webhooks.subscribers.apply_security_to_subscription`.

.. autofunction:: nti.webhooks.subscribers.apply_security_to_subscription
   :noindex:

Here's a demonstration using a
:class:`nti.webhooks.interfaces.IWebhookSubscriptionSecuritySetter`
that does nothing. When we create a new subscription for Bob, no one
(other than the manager, who inherits access) has any access.

.. doctest::

   >>> from nti.webhooks.interfaces import IWebhookSubscriptionSecuritySetter
   >>> from nti.webhooks.interfaces import IWebhookSubscription
   >>> from zope.interface import implementer
   >>> from nti.webhooks.subscriptions import resetGlobals
   >>> resetGlobals()
   >>> @component.adapter(IWebhookSubscription)
   ... @implementer(IWebhookSubscriptionSecuritySetter)
   ... class NoOpSetter(object):
   ...     def __init__(self, context, request=None):
   ...         pass
   ...     def __call__(self, context, event=None):
   ...         pass
   >>> from zope import component
   >>> component.provideAdapter(NoOpSetter)
   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <include package="nti.webhooks" />
   ...   <webhooks:staticSubscription
   ...             to="https://example.com/some/path"
   ...             for="zope.container.interfaces.IContentContainer"
   ...             when="zope.lifecycleevent.interfaces.IObjectCreatedEvent"
   ...             permission="zope.View"
   ...             owner="webhook.bob" />
   ... </configure>
   ... """)
   >>> subscription = sub_manager['Subscription']
   >>> checkPermissions('webhook.alice', subscription)
   Permissions(view=False, delete=False, other=False)
   >>> checkPermissions('webhook.bob', subscription)
   Permissions(view=False, delete=False, other=False)
   >>> checkPermissions('webhook.manager', subscription)
   Permissions(view=True, delete=True, other=True)

.. testcleanup::

   from zope.testing import cleanup
   cleanup.cleanUp()
