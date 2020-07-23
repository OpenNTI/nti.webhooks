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

Recall that the ``permission`` defined here is checked on objects that
trigger the subscription. It is not a permission for the subscription itself.

Access To The Subscription
==========================

The Alice principal has view and delete access to the subscription:

.. doctest::

   >>> from zope import component
   >>> from nti.webhooks import interfaces
   >>> from zope.security.testing import interaction
   >>> from zope.security import checkPermission
   >>> sub_manager = component.getUtility(interfaces.IWebhookSubscriptionManager)
   >>> subscription = sub_manager['Subscription']
   >>> with interaction('webhook.alice'):
   ...    checkPermission('zope.View', subscription)
   True
   >>> with interaction('webhook.alice'):
   ...    checkPermission('nti.actions.delete', subscription)
   True


The manager also has view and delete access, plus a bunch of other inherited things:

.. doctest::

   >>> with interaction('webhook.manager'):
   ...    checkPermission('zope.View', subscription)
   True
   >>> with interaction('webhook.manager'):
   ...    checkPermission('nti.actions.delete', subscription)
   True
   >>> with interaction('webhook.manager'):
   ...    checkPermission('zope.ManageContent', subscription)
   True

The other principal has no access:

.. doctest::


   >>> with interaction('webhook.bob'):
   ...    checkPermission('zope.View', subscription)
   False
   >>> with interaction('webhook.bob'):
   ...    checkPermission('nti.actions.delete', subscription)
   False
   >>> with interaction('webhook.bob'):
   ...    checkPermission('zope.ManageContent', subscription)
   False


.. todo:: Need to make sure to remove security proxies before adding
          delivery attempts? Test that.
.. todo:: Write a subscriber and example for when the owner_id
          changes. Currently that's forbidden by the docs.
.. todo:: Write test demonstrating that this flows down to delivery attempts.

.. testcleanup::

   from zope.testing import cleanup
   cleanup.cleanUp()
