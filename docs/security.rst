==========================
 Delivery Security Checks
==========================

In :doc:`static`, we discussed how to use ZCML to register for webhook
deliveries when certain events on certain resources happen.
Conspicuously absent from that discussion was any mention of two of
the more interesting and important attributes of the :class:`ZCML
directive <nti.webhooks.zcml.IStaticSubscriptionDirective>`:
``owner`` and ``permission``. This document will fill in those
details.

Owners
======

Owners, for both static subscriptions and other types of
subscriptions, are strings naming a :mod:`IPrincipal
<zope.security.interfaces>` as defined in
:mod:`zope.security.interfaces`. At runtime, the string is turned into
an ``IPrincipal`` object using
:meth:`zope.authentication.interfaces.IAuthentication.getPrincipal`
from the :mod:`IAuthentication <zope.authentication.interfaces>`
utility *closest to the object of the event* (i.e., the ``for`` part
of the directive).

.. note::

   ``IAuthentication`` utilities are usually arranged
   into a hierarchy related to the object hierarchy, and principals may
   exist in some parts of the tree and not in others. (While steps such
   as prefixing the principal ID are usually taken to avoid having the
   same principal ID be valid in two different parts of the site
   hierarchy but mean two completely different principals, that is a
   valid possibility.)

If no principal can be found, the unauthenticated (anonymous)
principal will be used instead; depending on the security policy and
permission structure in use, the subscription may or may not be
:term:`applicable`.


Permissions
===========

Permissions are defined by :mod:`IPermission
<zope.security.interfaces>`, but the important part is how they are
checked.

The :mod:`ISecurityPolicy <zope.security.interfaces>` is used to
produce an ``IInteraction`` object. The ``IInteraction`` is then asked
to confirm the permission using its ``checkPermission(permission,
object)`` method. Normally, the security policy is a global object,
and there can only be one active interaction at a time, but temporary,
sub-interactions are possible. This module follows that model.

.. important::

   When creating the temporary interactions to check permissions, this
   module will use the global security policy to create an interaction
   containing *two* participations: one for the principal found
   relating to the object, and one for the principal that was
   previously participating, if there was one. In this way, the
   permission must be allowed to both the *initiator* of the action
   (the logged in user) as well as the owner of the subscription.

Example
=======

Lets put these pieces together and check how security applies.

We'll begin by defining the same subscription we used :doc:`previously
<static>`, but we'll establish a security policy, and require a
permission and owner for the subscription. We'll use
:mod:`zope.principalregistry` to provide a global ``IAuthentication``
utility; this also provides a global ``IUnauthenticatedPrincipal``
that is used if the ``owner`` cannot be found at runtime:

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
   ...   <include package="zope.securitypolicy" file="securitypolicy.zcml" />
   ...   <include package="nti.webhooks" />
   ...   <include package="nti.webhooks" file="subscribers_promiscuous.zcml" />
   ...   <webhooks:staticSubscription
   ...             to="https://this_domain_does_not_exist"
   ...             for="zope.container.interfaces.IContentContainer"
   ...             when="zope.lifecycleevent.interfaces.IObjectCreatedEvent"
   ...             permission="zope.View"
   ...             owner="some.one" />
   ... </configure>
   ... """)

Next, we can find the :term:`active` subscription, just as before:

   >>> from nti.webhooks.subscribers import find_active_subscriptions_for
   >>> from zope.container.folder import Folder
   >>> from zope.lifecycleevent import ObjectCreatedEvent
   >>> event = ObjectCreatedEvent(Folder())
   >>> len(find_active_subscriptions_for(event.object, event))
   1
   >>> find_active_subscriptions_for(event.object, event)
   [<...Subscription ... to='https://this_domain_does_not_exist' for=IContentContainer when=IObjectCreatedEvent>]

.. _default-view-access:

Subscription Is Not Applicable By Default
-----------------------------------------

Next, we need to know if the subscription is :term:`applicable` to the
data. Unlike before, since we have security constraints in place, the
subscription is *not* applicable:

.. doctest::

   >>> subscriptions = find_active_subscriptions_for(event.object, event)
   >>> [subscription.isApplicable(event.object) for subscription in subscriptions]
   [True]

Wait, wait...what happened there? It turns out that since we don't
have any defined principal identified by ``some.one``, we use the
global ``IUnauthenticatedPrincipal``, an anonymous user. In turn, the
directives executed by loading ``securitypolicy.zcml`` from
``zope.securitypolicy`` give anonymous users the ``zope.View``
permission by default. Let's reverse that and check again.

.. doctest::

   >>> from zope.securitypolicy.rolepermission import rolePermissionManager
   >>> rolePermissionManager.denyPermissionToRole('zope.View', 'zope.Anonymous')
   >>> [subscription.isApplicable(event.object) for subscription in subscriptions]
   [False]

Ahh, that's better. We could have also disabled that behaviour.

.. note:: Dynamic (persistent) subscriptions do not fallback to the unauthenticated
          principal by default.

.. doctest::

   >>> subscriptions[0].fallback_to_unauthenticated_principal
   True
   >>> subscriptions[0].fallback_to_unauthenticated_principal = False


Subscription Applicable Once Principals are Defined
---------------------------------------------------

To grant access in an expected way, we'll use
``zope.principalregistry`` to globally define the prinicpal we're
looking for, as well as globally grant that principal the permissions
necessary:

   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <include package="zope.securitypolicy" file="meta.zcml" />
   ...   <include package="zope.principalregistry" file="meta.zcml" />
   ...   <principal
   ...         id="some.one"
   ...         title="Some One"
   ...         login="some.one"
   ...         password_manager="SHA1"
   ...         password="40bd001563085fc35165329ea1ff5c5ecbdbbeef"
   ...         />
   ...   <grant principal="some.one" permission="zope.View" />
   ... </configure>
   ... """)

Now our webhook is :term:`applicable`:

.. doctest::

   >>> [subscription.isApplicable(event.object) for subscription in subscriptions]
   [True]

Existing Interactions
---------------------

If there was already an interaction going on (e.g., for the logged in
user that created the object), the owner of the subscription is added
to that interaction for purposes of checking permissions. Security
policies generally only grant access if all participations in the
interaction have access.

We'll demonstrate this by creating and acting as a new principal and
then checking access. Because our new user has no permissions on the
object being created (which of course is highly unusual), the
permission check will fail.

.. doctest::

   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <include package="zope.principalregistry" file="meta.zcml" />
   ...   <principal
   ...         id="some.one.else"
   ...         title="Some One Else"
   ...         login="some.one.else"
   ...         password_manager="SHA1"
   ...         password="40bd001563085fc35165329ea1ff5c5ecbdbbeef"
   ...         />
   ... </configure>
   ... """)
   >>> from zope.security.testing import interaction
   >>> with interaction('some.one.else'):
   ...    [subscription.isApplicable(event.object) for subscription in subscriptions]
   [False]

Automatic Deactivation On Failure
=================================

For any type of subscription (static, dynamic, persistent, ...) that
implements
:class:`nti.webhooks.interfaces.ILimitedApplicabilityPreconditionFailureWebhookSubscription`,
attempting to make deliveries to it while it is misconfigured (e.g.,
there is no such permission defined or no principal can be found) will
eventually result in it becoming automatically disabled.

Our subscription is such an object:

.. doctest::

   >>> from nti.webhooks.interfaces import ILimitedApplicabilityPreconditionFailureWebhookSubscription
   >>> from zope.interface import verify
   >>> subscription = subscriptions[0]
   >>> verify.verifyObject(ILimitedApplicabilityPreconditionFailureWebhookSubscription, subscription)
   True
   >>> subscription.applicable_precondition_failure_limit
   50
   >>> subscription.active
   True
   >>> print(subscription.status_message)
   Active

This doesn't apply when the permission check is simply denied; that's
normal and expected.

.. doctest::

   >>> from delivery_helper import deliver_some
   >>> from nti.webhooks.testing import wait_for_deliveries
   >>> with interaction('some.one.else'):
   ...      deliver_some(100)
   >>> len(subscription)
   0
   >>> subscription.active
   True

But if we remove the principal our subscription is using (being
careful not to fire any events that might automatically remove or
deactivate the subscription) we can see that it becomes inactive at
the correct time.

First, we'll deliver one, just to prove it works.

.. doctest::

   >>> deliver_some()
   >>> wait_for_deliveries()
   >>> len(subscription)
   1

Now we'll destroy the principal registration, making this object
incapable of accepting deliveries. (This works because we disabled the
fallback to the unauthenticated principal earlier.)

.. doctest::

   >>> from zope.principalregistry import principalregistry
   >>> principalregistry.principalRegistry._clear()

When we attempt enough of them, it is deactivated.

.. doctest::

   >>> deliver_some(49)
   >>> len(subscription)
   1
   >>> subscription.active
   True
   >>> deliver_some(2)
   >>> len(subscription)
   1
   >>> subscription.active
   False
   >>> print(subscription.status_message)
   Delivery suspended due to too many precondition failures.

Manually activating the subscription resets the counter.

.. doctest::

   >>> subscription.__parent__.activateSubscription(subscription)
   True
   >>> subscription.active
   True
   >>> print(subscription.status_message)
   Active
   >>> deliver_some(50)
   >>> subscription.active
   False

.. testcleanup::

   from zope.testing import cleanup
   cleanup.cleanUp()
