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

.. XXX: Remember to revisit these imports.

.. doctest::


   >>> from employees import Department, Office, ExternalizableEmployee as Employee
   >>> import transaction
   >>> from nti.webhooks.testing import ZODBFixture
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
    >>> dep_auth = department.getSiteManager()['default']['authentication'] = PluggableAuthentication('nws.')
    >>> department.getSiteManager().registerUtility(dep_auth, IAuthentication)
    >>> nws_principals = PrincipalFolder()
    >>> dbob_prin = nws_principals['bob'] = InternalPrincipal('login', 'password', 'title')
    >>> dep_auth['principals'] = nws_principals
    >>> dep_auth.authenticatorPlugins = ('principals',)
    >>> office_auth = office.getSiteManager()['default']['authentication'] = PluggableAuthentication('nws.oun.')
    >>> office.getSiteManager().registerUtility(office_auth, IAuthentication)
    >>> office_principals = PrincipalFolder()
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

.. testcleanup::

   from nti.webhooks.tests.test_docs import zodbTearDown
   zodbTearDown()
