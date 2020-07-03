=================
 Security Checks
=================

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

If no principal can be found, the subscription will not be
:term:`applicable` and no delivery will be attempted.

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
<static>`, but we'll add a permission and an owner. We'll use
:mod:`zope.principalregistry` to provide a global ``IAuthentication``
utility and a defined principal:

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
   ...   <include package="zope.principalregistry" file="meta.zcml" />
   ...   <include package="nti.webhooks" />
   ...   <principal
   ...         id="zope.manager"
   ...         title="Manager"
   ...         description="System Manager"
   ...         login="admin"
   ...         password_manager="SHA1"
   ...         password="40bd001563085fc35165329ea1ff5c5ecbdbbeef"
   ...         />
   ...   <webhooks:staticSubscription
   ...             to="https://this_domain_does_not_exist"
   ...             for="zope.container.interfaces.IContentContainer"
   ...             when="zope.lifecycleevent.interfaces.IObjectCreatedEvent"
   ...             permission="zope.View"
   ...             owner="zope.manager" />
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


Next, we need to know if the subscription is :term:`applicable` to the
data. Unlike before, since we have security constraints in place, the subscription is *not* applicable:

.. doctest::

   >>> subscriptions = find_active_subscriptions_for(event.object, event)
   >>> [subscription.isApplicable(event.object) for subscription in subscriptions]
   [False]