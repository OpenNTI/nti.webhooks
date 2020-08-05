========================
 Removing Subscriptions
========================

.. testsetup::

   from nti.webhooks.tests.test_docs import zodbSetUp
   zodbSetUp()


After having created subscriptions through the API (see
:doc:`dynamic`), there are circumstances under which we may want to
remove them. If we have the path to the subscription object, removing
it is easy: Just remove it from its parent container (which
can be obtained through traversal) as usual.

But there are other circumstances in which subscriptions should be
removed. This document outlines some of them and the support that this
package provides.

Principal Removal
=================

When a subscription is owned by a particular principal, usually we'll
want to remove it when the principal itself is removed from the
system.

To support this, this package provides a subscriber that handles
removing subscriptions owned by a principal.

.. important::

   Because this package can't know for sure what the appropriate event
   is, it provides no ZCML to register this subscriber. You are
   responsible for making that registration.

We'll demonstrate this by setting up a site tree similarly to how it
was done in :doc:`dynamic`.

First, the common imports and a ZODB database. This is the same as in
:doc:`dynamic`, except that we're also configuring
:mod:`zope.pluggableauth` because we'll use that to be our principal
implementation (in turn, that needs ``zope.password``); configuring
``zope.securitypolicy`` is needed here because, unlike in that
document, we'll be specifying subscription owners and we need the
adapters to be able to configure the security settings for those
objects.


.. doctest::


   >>> from employees import Department, Office, ExternalizableEmployee as Employee
   >>> import transaction
   >>> from nti.webhooks.testing import DoctestTransaction
   >>> from nti.webhooks.testing import mock_delivery_to
   >>> from nti.site.hostpolicy import install_main_application_and_sites
   >>> from nti.site.testing import print_tree
   >>> from zope.traversing import api as ztapi
   >>> from zope.configuration import xmlconfig
   >>> mock_delivery_to('https://example.com/some/path', method='POST', status=200)
   >>> mock_delivery_to('https://example.com/another/path', method='POST', status=404)
   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <include package="nti.webhooks" />
   ...   <include package="nti.webhooks" file="subscribers_promiscuous.zcml" />
   ...   <include package="nti.site" />
   ...   <include package="zope.traversing" />
   ...   <include package="zope.pluggableauth" />
   ...   <include package="zope.pluggableauth.plugins" file="principalfolder.zcml" />
   ...   <include package="zope.password" />
   ...   <include package="zope.securitypolicy" />
   ...   <include package="zope.securitypolicy" file="securitypolicy.zcml" />
   ... </configure>
   ... """)

Next, we duplicate our site setup, including creating two employee
objects.

.. doctest::

   >>> tx = DoctestTransaction()
   >>> conn = tx.begin()
   >>> root_folder, main_folder = install_main_application_and_sites(
   ...        conn,
   ...        root_alias=None, main_name='NOAA', main_alias=None)
   >>> department = main_folder['NWS'] = Department()
   >>> office = department['OUN'] = Office()
   >>> department_bob = department['employees']['Bob'] = Employee()
   >>> office_bob = office['employees']['Bob'] = Employee()
   >>> print_tree(root_folder, depth=0, details=())
   <ISite,IRootFolder>: <zope.site.folder.Folder object...>
        <ISite,IMainApplicationFolder>: NOAA
            ++etc++hostsites
            <ISite>: NWS
                <ISite>: OUN
                    employees
                        Bob => <Employee Bob 1>
                employees
                    Bob => <Employee Bob 0>

We'll then create corresponding principals for these two employees
using :mod:`zope.pluggableauth.plugins.principalfolder`.

.. doctest::

    >>> from zope.authentication.interfaces import IAuthentication
    >>> from zope.pluggableauth.interfaces import IAuthenticatorPlugin
    >>> from zope.pluggableauth.authentication import PluggableAuthentication
    >>> from zope.pluggableauth.plugins.principalfolder import PrincipalFolder
    >>> from zope.pluggableauth.plugins.principalfolder import InternalPrincipal
    >>> dep_auth = department.getSiteManager()['default']['authentication'] = PluggableAuthentication()
    >>> department.getSiteManager().registerUtility(dep_auth, IAuthentication)
    >>> nws_principals = PrincipalFolder('nws.')
    >>> dbob_prin = nws_principals['bob'] = InternalPrincipal('login', 'password', 'title')
    >>> dep_auth['principals'] = nws_principals
    >>> dep_auth.authenticatorPlugins = ('principals',)
    >>> office_auth = office.getSiteManager()['default']['authentication'] = PluggableAuthentication()
    >>> office.getSiteManager().registerUtility(office_auth, IAuthentication)
    >>> office_principals = PrincipalFolder('nws.oun.')
    >>> obob_prin = office_principals['bob'] = InternalPrincipal('login', 'password', 'title')
    >>> office_auth['principals'] = office_principals
    >>> office_auth.authenticatorPlugins = ('principals',)
    >>> print_tree(root_folder, depth=0, details=('siteManager',))
    <ISite,IRootFolder>: <zope.site.folder.Folder ...>
         <ISite,IMainApplicationFolder>: NOAA
             ++etc++hostsites
             <ISite>: NWS
                 <ISite>: OUN
                     employees
                         Bob => <Employee Bob 1>
                     <Site Manager> name=++etc++site
                         default
                             authentication
                                 principals
                                     bob => <....InternalPrincipal object ...>
                 employees
                     Bob => <Employee Bob 0>
                 <Site Manager> name=++etc++site
                     default
                         authentication
                             principals
                                 bob => <...InternalPrincipal object ...>
             <Site Manager> name=++etc++site
                 default
         <Site Manager> name=++etc++site
             default

The lowest level principal folder can resolve both principals, but the higher level
can resolve only the one defined at that level. Note how prefixes have been attached to the
principal IDs.

.. doctest::

   >>> office_auth.getPrincipal('nws.oun.bob')
   Principal('nws.oun.bob')
   >>> office_auth.getPrincipal('nws.bob')
   Principal('nws.bob')
   >>> dep_auth.getPrincipal('nws.bob')
   Principal('nws.bob')
   >>> dep_auth.getPrincipal('nws.oun.bob')
   Traceback (most recent call last):
   ...
   zope.authentication.interfaces.PrincipalLookupError: oun.bob


Now that we have principals, with IDs, lets have them each subscribe
to their own employee object, and commit the transaction.

.. doctest::

    >>> from nti.webhooks.api import subscribe_to_resource
    >>> obob_sub = subscribe_to_resource(office_bob, 'https://example.com/some/path',
    ...    owner_id=u'nws.oun.bob', permission_id='zope.View')
    >>> obob_sub
    <...PersistentSubscription ... to='https://example.com/some/path' for=employees.ExternalizableEmployee when=IObjectEvent>
    >>> dbob_sub = subscribe_to_resource(department_bob, 'https://example.com/another/path',
    ...    owner_id=u'nws.bob', permission_id='zope.View')
    >>> dbob_sub
    <...PersistentSubscription ... to='https://example.com/another/path' for=employees.ExternalizableEmployee when=IObjectEvent>
    >>> print_tree(root_folder, depth=0, details=('siteManager'))
    <ISite,IRootFolder>: <zope.site.folder.Folder ...>
         <ISite,IMainApplicationFolder>: NOAA
             ++etc++hostsites
             <ISite>: NWS
                 <ISite>: OUN
                     employees
                         Bob => <Employee Bob 1>
                     <Site Manager> name=++etc++site
                         default
                             WebhookSubscriptionManager
                                 PersistentSubscription
                             authentication
                                 principals
                                     bob => ...
                 employees
                     Bob => <Employee Bob 0>
                 <Site Manager> name=++etc++site
                     default
                         WebhookSubscriptionManager
                             PersistentSubscription
                         authentication
                             principals
                                 bob => ...
             <Site Manager> name=++etc++site
                 default
         <Site Manager> name=++etc++site
             default
    >>> tx.finish()

Lets deliver some hooks to both subscriptions in order to have
something to look at.

.. doctest::

   >>> from nti.webhooks.testing import begin_synchronous_delivery
   >>> begin_synchronous_delivery()
   >>> def trigger_delivery():
   ...    from zope import lifecycleevent, component
   ...    from nti.webhooks.interfaces import IWebhookDeliveryManager
   ...    conn = tx.begin()
   ...    office_bob_path = '/NOAA/NWS/OUN/employees/Bob'
   ...    office_bob = ztapi.traverse(conn.root()['Application'], office_bob_path)
   ...    lifecycleevent.modified(office_bob)
   ...    tx.finish()
   ...    component.getUtility(IWebhookDeliveryManager).waitForPendingDeliveries()
   >>> from zope.security.testing import interaction
   >>> with interaction('nws.oun.bob'):
   ...     trigger_delivery()
   >>> with interaction('nws.bob'):
   ...     trigger_delivery()

We used the office Bob as the context, so both subscriptions were
found. And we specified ``zope.View`` as the permission, which by
default is granted to everyone authenticated principal. Thus, both
subscriptions have recorded two delivery attempts.

.. doctest::

   >>> _ = tx.begin()
   >>> len(obob_sub)
   2
   >>> len(dbob_sub)
   2
   >>> tx.finish()


Registering The Handler
-----------------------

Lets register the handler and pretend to remove a principal. Hopefully the
matching subscriptions are removed too.

.. autofunction:: nti.webhooks.subscribers.remove_subscriptions_for_principal
   :noindex:

.. doctest::

    >>> from nti.webhooks.subscribers import remove_subscriptions_for_principal
    >>> from zope import component
    >>> from zope.lifecycleevent import removed
    >>> component.provideHandler(remove_subscriptions_for_principal)
    >>> _ = tx.begin()
    >>> removed(obob_prin)
    >>> print_tree(department, depth=0, details=('siteManager',))
    <ISite>: NWS
         <ISite>: OUN
             employees
                 Bob => <Employee Bob 1>
             <Site Manager> name=++etc++site
                 default
                     WebhookSubscriptionManager
                         PersistentSubscription
                             ... => <...PersistentWebhookDeliveryAttempt ... status='successful'>
                             ... => <...PersistentWebhookDeliveryAttempt ... status='successful'>
                     authentication
                         principals
                             bob => <....InternalPrincipal object ...>
         employees
             Bob => <Employee Bob 0>
         <Site Manager> name=++etc++site
             default
                 WebhookSubscriptionManager
                     PersistentSubscription
                         ... => <...PersistentWebhookDeliveryAttempt ... status='failed'>
                         ... => <...PersistentWebhookDeliveryAttempt ... status='failed'>
                 authentication
                     principals
                         bob => <....InternalPrincipal object ...>

They weren't. In fact, the subscriber didn't even run. Why not?

It turns out the ``InternalPrincipal`` objects don't implement
``IPrincipal``, so, as the docstring warned, the default registration
wasn't suitable here. We can fix that and try again.

.. doctest::

    >>> from zope.pluggableauth.plugins.principalfolder import IInternalPrincipal
    >>> from zope.lifecycleevent.interfaces import IObjectRemovedEvent
    >>> component.provideHandler(remove_subscriptions_for_principal,
    ...                          (IInternalPrincipal, IObjectRemovedEvent))
    >>> removed(obob_prin)
    Traceback (most recent call last):
    ...
    AttributeError: 'InternalPrincipal' object has no attribute 'id'

Narf. Also as the docstring warned, the object being removed isn't
actually a ``IPrincipal`` and doesn't have a compatible interface. We can fix that
too! Since it should work this time, we'll actually remove the principal.

.. doctest::

    >>> from nti.webhooks.interfaces import IWebhookPrincipal
    >>> from zope.interface import implementer
    >>> @implementer(IWebhookPrincipal)
    ... @component.adapter(IInternalPrincipal)
    ... class InternalPrincipalWebhookPrincipal(object):
    ...    def __init__(self, context):
    ...        self.id = context.__parent__.getIdByLogin(context.login)
    >>> component.provideAdapter(InternalPrincipalWebhookPrincipal)
    >>> del office_principals['bob']
    >>> print_tree(department, depth=0, details=('siteManager',))
    <ISite>: NWS
         <ISite>: OUN
             employees
                 Bob => <Employee Bob 1>
             <Site Manager> name=++etc++site
                 default
                     WebhookSubscriptionManager
                     authentication
                         principals
         employees
             Bob => <Employee Bob 0>
         <Site Manager> name=++etc++site
             default
                 WebhookSubscriptionManager
                     PersistentSubscription
                         ... => <...PersistentWebhookDeliveryAttempt ... status='failed'>
                         ... => <...PersistentWebhookDeliveryAttempt ... status='failed'>
                 authentication
                     principals
                         bob => <....InternalPrincipal object ...>
    >>> tx.finish()

There! That did it.


Subscription Managers Outside The Site and Lineage
--------------------------------------------------

The documentation for :func:`~.remove_subscriptions_for_principal`
mentions that only subscription managers in the current site
hierarchy, and the hierarchy of the principal being removed, can be
removed automatically. If there are subscriptions located outside this area,
they won't be removed. We can demonstrate this by setting up
such a subscription. First, we need to add a new site; once that's done, we can
add the subscription and commit.

.. doctest::

    >>> from nti.webhooks.api import subscribe_in_site_manager
    >>> _ = tx.begin()
    >>> office = department['AMA'] = Office()
    >>> subscribe_in_site_manager(office.getSiteManager(),
    ...    dict(to='https://example.com', for_=type(office_bob),
    ...         when=IObjectRemovedEvent, owner_id=u'nws.bob'))
    <....PersistentSubscription ...>
    >>> print_tree(department, depth=0, details=('siteManager',))
    <ISite>: NWS
         <ISite>: AMA
             employees
             <Site Manager> name=++etc++site
                 default
                     WebhookSubscriptionManager
                         PersistentSubscription
         <ISite>: OUN
             employees
                 Bob => <Employee Bob 1>
             <Site Manager> name=++etc++site
                 default
                     WebhookSubscriptionManager
                     authentication
                         principals
         employees
             Bob => <Employee Bob 0>
         <Site Manager> name=++etc++site
             default
                 WebhookSubscriptionManager
                     PersistentSubscription
                         ... => <...PersistentWebhookDeliveryAttempt ... status='failed'>
                         ... => <...PersistentWebhookDeliveryAttempt ... status='failed'>
                 authentication
                     principals
                         bob => <....InternalPrincipal object ...>
    >>> tx.finish()

Now what happens when we delete "nws.bob"? That principal is *above*
the subscription that was just created.

.. doctest::

    >>> _ = tx.begin()
    >>> del nws_principals['bob']
    >>> print_tree(department, depth=0, details=('siteManager',))
    <ISite>: NWS
         <ISite>: AMA
             employees
             <Site Manager> name=++etc++site
                 default
                     WebhookSubscriptionManager
                         PersistentSubscription
         <ISite>: OUN
             employees
                 Bob => <Employee Bob 1>
             <Site Manager> name=++etc++site
                 default
                     WebhookSubscriptionManager
                     authentication
                         principals
         employees
             Bob => <Employee Bob 0>
         <Site Manager> name=++etc++site
             default
                 WebhookSubscriptionManager
                 authentication
                     principals
    >>> tx.abort()

We can see that we deleted the principal, and the subscription at the same level, but
we didn't find the unrelated subscription.

The solution to this is generally application specific. You can either
listen for the event yourself, or register an appropriate
:class:`nti.webhooks.interfaces.IWebhookSubscriptionManagers` adapter. For
simple, small, applications, the
:class:`nti.webhooks.subscribers.ExhaustiveWebhookSubscriptionManagers` can be used.

.. doctest::

    >>> from nti.webhooks.subscribers import ExhaustiveWebhookSubscriptionManagers
    >>> component.provideAdapter(ExhaustiveWebhookSubscriptionManagers, (IInternalPrincipal,))
    >>> _ = tx.begin()
    >>> del nws_principals['bob']
    >>> print_tree(department, depth=0, details=('siteManager',))
    <ISite>: NWS
         <ISite>: AMA
             employees
             <Site Manager> name=++etc++site
                 default
                     WebhookSubscriptionManager
         <ISite>: OUN
             employees
                 Bob => <Employee Bob 1>
             <Site Manager> name=++etc++site
                 default
                     WebhookSubscriptionManager
                     authentication
                         principals
         employees
             Bob => <Employee Bob 0>
         <Site Manager> name=++etc++site
             default
                 WebhookSubscriptionManager
                 authentication
                     principals
    >>> tx.finish()


.. testcleanup::

   from nti.webhooks.tests.test_docs import zodbTearDown
   zodbTearDown()
