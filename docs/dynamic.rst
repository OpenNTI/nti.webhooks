===============================
 Dynamic Webhook Subscriptions
===============================

In addition to static webhook subscriptions defined in ZCML, this
package supports dynamic webhook subscriptions created, activated,
inactivated, and removed through code at runtime. Such subscriptions,
and their delivery history, are typically :class:`persistent
<persistent.Persistent>` in the ZODB sense of the word.

Subscriptions are managed via an implementation of
:class:`nti.webhooks.interfaces.IWebhookSubscriptionManager`. We've
already seen (in :doc:`static`) how there is a global, non-persistent
subscription manager installed by default. This document explores
issues around persistent, local subscription managers.

Goals
=====

Persistent subscription managers, and their subscriptions and in turn
delivery histories, should:

- Have complete paths, as defined by
  :meth:`zope.location.interfaces.ILocationInfo.getPath` or
  :meth:`zope.traversing.interfaces.ITraversalAPI.getPath`.
- Be fully traversable, as defined by
  :meth:`zope.traversing.interfaces.ITraversalAPI.traverseName`.

This second requirement is met by having the subscription manager be a
:class:`zope.container.interfaces.IContainer` of
``IWebhookSubscription`` objects, which in turn are containers
of ``IWebhookDeliveryAttempt`` objects.

The first requirement is somewhat harder. This package offers a
high-level API to help with it, integrated with :mod:`nti.site`. In
this API, persistent webhook subscription managers are stored in the
site manager using :func:`nti.site.localutility.install_utility` with
a name in the :class:`etc <zope.traversing.namespace.etc>` namespace.

.. doctest::
   :hide:

   >>> from zope.configuration import xmlconfig
   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <include package="nti.webhooks" />
   ...   <include package="nti.site" />
   ...   <include package="zope.traversing" />
   ... </configure>
   ... """)
   >>> from zope.component.hooks import setHooks
   >>> setHooks()
   >>> import nti.webhooks.testing
   >>> __name__ = 'nti.webhooks.testing'


Setup
=====

To begin, we will provide a persistent site hierarchy with traversable
paths. Following the example from the main documentation, we'll create
a department named "NWS" and office named "OUN", plus some people
in each one. The department and office will be sites, with a site manager.

First define the classes.

.. doctest::

   >>> from persistent import Persistent
   >>> from zope.container.contained import Contained
   >>> from zope.site.folder import Folder
   >>> from zope.site import LocalSiteManager
   >>> class Employees(Folder):
   ...    def __init__(self):
   ...        Folder.__init__(self)
   ...        self['employees'] = Folder()
   ...        self.setSiteManager(LocalSiteManager(self))
   >>> class Department(Employees):
   ...     pass
   >>> class Office(Employees):
   ...     pass
   >>> class Employee(Contained, Persistent):
   ...    pass

.. doctest::
   :hide:

   >>> nti.webhooks.testing.Department = Department
   >>> nti.webhooks.testing.Office = Office
   >>> nti.webhooks.testing.Employee = Employee

Now we'll create a database and store our hierarchy.

.. doctest::

   >>> import transaction
   >>> from ZODB import DB
   >>> from ZODB.DemoStorage import DemoStorage
   >>> from nti.site.hostpolicy import install_main_application_and_sites
   >>> from nti.site.testing import print_tree
   >>> db = DB(DemoStorage())
   >>> _ = transaction.begin()
   >>> conn = db.open()
   >>> root_folder, main_folder = install_main_application_and_sites(
   ...        conn,
   ...        root_alias=None, main_name='NOAA', main_alias=None)
   >>> department = main_folder['NWS'] = Department()
   >>> office = department['OUN'] = Office()
   >>> department_bob = department['employees']['Bob'] = Employee()
   >>> office_bob = office['employees']['Bob'] = Employee()
   >>> print_tree(root_folder)
        <ISite,IRootFolder>: <zope.site.folder.Folder object ...>
            <ISite,IMainApplicationFolder>: NOAA ...
                ++etc++hostsites ...
                <ISite>: NWS ...
                    <ISite>: OUN ...
                        employees ...
                            Bob ...
                            ...
                    employees ...
                        Bob ...
                            ...
   >>> from zope.traversing import api as ztapi
   >>> print(ztapi.getPath(office_bob))
   /NOAA/NWS/OUN/employees/Bob
   >>> transaction.commit()

High-level API
==============

The high-level API lets us create subscriptions based on a resource,
frequently one we've traversed to.

.. autofunction:: nti.webhooks.api.subscribe_to_resource
   :noindex:

.. doctest::

   >>> from nti.webhooks.api import subscribe_to_resource
   >>> _ = transaction.begin()
   >>> subscription = subscribe_to_resource(office_bob, 'https://example.com/some/path')
   >>> subscription
   <...PersistentSubscription at 0x... to='https://example.com/some/path' for=nti.webhooks.testing.Employee when=IObjectEvent>
   >>> transaction.commit()

By looking at the path, we can see that a subscription manager
containing the subscription was created at the closest enclosing site
manager. We can also traverse this path to get back to the subscription, and its
manager:

.. doctest::

   >>> path = ztapi.getPath(subscription)
   >>> print(path)
   /NOAA/NWS/OUN/++etc++site/WebhookSubscriptionManager/PersistentSubscription
   >>> ztapi.traverse(root_folder, path) is subscription
   True
   >>> ztapi.traverse(root_folder, '/NOAA/NWS/OUN/++etc++site/WebhookSubscriptionManager')
   <....PersistentWebhookSubscriptionManager object at 0x...>

Even though the office that contains this subscription is not the current site,
we can still find this subscription and confirm that it is active.

.. doctest::

   >>> from zope.component import getSiteManager
   >>> getSiteManager() is office.getSiteManager()
   False
   >>> from nti.webhooks.subscribers import find_active_subscriptions_for
   >>> from zope.lifecycleevent import ObjectModifiedEvent
   >>> event = ObjectModifiedEvent(office_bob)
   >>> len(find_active_subscriptions_for(event.object, event))
   1
   >>> find_active_subscriptions_for(event.object, event)[0] is subscription
   True

A static subscription registered globally is also found:

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
   ...             for="nti.webhooks.testing.Employee"
   ...             when="zope.lifecycleevent.interfaces.IObjectModifiedEvent" />
   ... </configure>
   ... """)
   >>> event = ObjectModifiedEvent(office_bob)
   >>> subscriptions = find_active_subscriptions_for(event.object, event)
   >>> len(subscriptions)
   2
   >>> subscriptions
   [<...Subscription at 0x... to='https://this_domain_does_not_exist' for=Employee when=IObjectModifiedEvent>, <...PersistentSubscription at 0x... to='https://example.com/some/path' ... when=IObjectEvent>]

TODO
====

- Removing subscriptions when principals are removed.
- Add test to add new subscription when manager already exists.
- Add subscription at higher level and find it too.


.. testcleanup::

   #using_mocks.finish()
   from zope.testing import cleanup
   cleanup.cleanUp()
