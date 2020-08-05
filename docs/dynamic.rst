===============================
 Dynamic Webhook Subscriptions
===============================

.. testsetup::

   from nti.webhooks.tests.test_docs import zodbSetUp
   zodbSetUp()


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

.. rubric:: Sub-pages

This page has sub-pages for specific topics.

.. toctree::

   dynamic/customizing_for


Setup
=====

To begin, we will provide a persistent site hierarchy with traversable
paths. Following the example from the main documentation, we'll create
a department named "NWS" and office named "OUN", plus some people
in each one. The department and office will be sites, with a site manager.

First define the classes. These are stored in a module named ``employees``.

.. literalinclude:: employees.py

.. doctest::

   >>> from employees import Department, Office, ExternalizableEmployee as Employee


Now we'll create a database and store our hierarchy.

.. note::

   The :class:`nti.webhooks.testing.ZODBFixture` establishes a
   global, unnamed, utility for the :class:`ZODB.interfaces.IDatabase`
   that it opens. This is what things like ``zope.app.appsetup`` do as well;
   your application needs to arrange for that utility to be available.

   The :func:`nti.site.runner.run_job_in_site` function also has this
   requirement.

Begin with some common imports and set up the required packages and fixture.

.. doctest::

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
   ... </configure>
   ... """)

Next, start a transaction and get a database connection, and add our
objects. We can show that we have a traversable path to the lowest
level object; we'll use this path to refer to that object in the
future (we don't keep a reference to the actual object because we'll
be opening and closing multiple transactions).

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
   >>> office_bob_path = ztapi.getPath(office_bob)
   >>> print(office_bob_path)
   /NOAA/NWS/OUN/employees/Bob
   >>> tx.finish()

High-level API
==============

The high-level API lets us create subscriptions based on a resource,
frequently one we've traversed to.

.. autofunction:: nti.webhooks.api.subscribe_to_resource
   :noindex:

.. doctest::

   >>> from nti.webhooks.api import subscribe_to_resource
   >>> conn = tx.begin()
   >>> office_bob = ztapi.traverse(conn.root()['Application'], office_bob_path)
   >>> subscription = subscribe_to_resource(office_bob, 'https://example.com/some/path')
   >>> subscription
   <...PersistentSubscription at 0x... to='https://example.com/some/path' for=employees.ExternalizableEmployee when=IObjectEvent>

What Just Happened
------------------

Several things happened here. The next sections will detail them.

A Subscription Manager Was Created
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

First, by getting the path to the subscription, we can see that a
subscription manager containing the subscription was created at the
closest enclosing site manager. We can also traverse this path to get
back to the subscription, and its manager:

.. doctest::

   >>> path = ztapi.getPath(subscription)
   >>> print(path)
   /NOAA/NWS/OUN/++etc++site/default/WebhookSubscriptionManager/PersistentSubscription
   >>> ztapi.traverse(root_folder, path) is subscription
   True
   >>> ztapi.traverse(root_folder, '/NOAA/NWS/OUN/++etc++site/default/WebhookSubscriptionManager')
   <....PersistentWebhookSubscriptionManager object at 0x...>

The ``for`` Was Inferred
~~~~~~~~~~~~~~~~~~~~~~~~

The API automatically deduced the value to use for ``for``, in this
case the same thing that ``office_bob`` provides:

.. doctest::

   >>> from zope.interface import providedBy
   >>> subscription.for_
   <implementedBy employees.ExternalizableEmployee>
   >>> subscription.for_.__name__
   'employees.ExternalizableEmployee'
   >>> providedBy(office_bob)
   <implementedBy employees.ExternalizableEmployee>
   >>> providedBy(office_bob).inherit
   <class 'employees.ExternalizableEmployee'>

This is a complex value; because of how pickling works, it will stay
in sync with exactly what that class actually provides.

.. doctest::

   >>> list(providedBy(office_bob).flattened())
   [<InterfaceClass ...IContained>, <InterfaceClass ...ILocation>, <InterfaceClass ...IPersistent>, <InterfaceClass ...Interface>]
   >>> import pickle
   >>> pickle.loads(pickle.dumps(subscription.for_)) is providedBy(office_bob)
   True

For instructions on customizing how this is inferred, see :doc:`dynamic/customizing_for`.


The ``when`` Was Guessed
~~~~~~~~~~~~~~~~~~~~~~~~

.. note::

   The value for ``when``, ``IObjectEvent``, may not be what you want.
   This may change in the future. See :doc:`configuration` for more
   information.

.. caution::

   This may change in the future. While it might be nice to have a
   single subscription that is ``when`` any of a group of events
   fires, the Zapier API prefers to have one subscription per event
   type. (TODO: Confirm this.) If that's the case, then there might be
   a higher-level concept to group related subscriptions together.

The Subscription is Active
~~~~~~~~~~~~~~~~~~~~~~~~~~

Even though the office that contains this subscription is not the current site,
we can still find this subscription and confirm that it is active.

.. doctest::

   >>> def subscriptions_for_bob(conn):
   ...     from nti.webhooks.subscribers import find_active_subscriptions_for
   ...     from zope.lifecycleevent import ObjectModifiedEvent
   ...     office_bob = ztapi.traverse(conn.root()['Application'], office_bob_path)
   ...     event = ObjectModifiedEvent(office_bob)
   ...     return find_active_subscriptions_for(event.object, event)
   >>> from zope.component import getSiteManager
   >>> getSiteManager() is office.getSiteManager()
   False
   >>> len(subscriptions_for_bob(conn))
   1
   >>> subscriptions_for_bob(conn)[0] is subscription
   True
   >>> tx.finish()

Relation To Static Subscriptions
--------------------------------

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
   ...             to="https://example.com/another/path"
   ...             for="employees.Employee"
   ...             when="zope.lifecycleevent.interfaces.IObjectModifiedEvent" />
   ... </configure>
   ... """)
   >>> conn = tx.begin()
   >>> subscriptions = subscriptions_for_bob(conn)
   >>> len(subscriptions)
   2
   >>> subscriptions
   [<...Subscription at 0x... to='https://example.com/another/path' for=Employee when=IObjectModifiedEvent>, <...PersistentSubscription at 0x... to='https://example.com/some/path' ... when=IObjectEvent>]
   >>> tx.finish()


Delivery to Static and Dynamic Subscriptions
--------------------------------------------

Now we can attempt delivery to these subscriptions. They will have a
delivery attempt recorded, and in the case of the persistent
subscription, it will be persistent itself.

First, we define a helper function that will trigger and wait for the deliveries.
We also ensure that the deliveries happen in a deterministic order.

.. doctest::

   >>> from nti.webhooks.testing import begin_synchronous_delivery
   >>> begin_synchronous_delivery()
   >>> def trigger_delivery():
   ...    from zope import lifecycleevent, component
   ...    from nti.webhooks.interfaces import IWebhookDeliveryManager
   ...    conn = tx.begin()
   ...    office_bob = ztapi.traverse(conn.root()['Application'], office_bob_path)
   ...    lifecycleevent.modified(office_bob)
   ...    tx.finish()
   ...    component.getUtility(IWebhookDeliveryManager).waitForPendingDeliveries()


Next, we deliver the events, and then fetch the updated subscriptions.

.. doctest::

   >>> trigger_delivery()
   >>> conn = tx.begin()
   >>> subscriptions = subscriptions_for_bob(conn)
   >>> subscriptions
   [<...Subscription at 0x... to='https://example.com/another/path' for=Employee when=IObjectModifiedEvent>, <...PersistentSubscription at 0x... to='https://example.com/some/path' ... when=IObjectEvent>]
   >>> global_subscription = subscriptions[0]
   >>> persistent_subscription = subscriptions[1]

Our attempt at persistent delivery was successful.

.. doctest::

   >>> attempt = persistent_subscription.pop()
   >>> print(attempt.status)
   successful
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
    'Content-Length': '5',
    'Content-Type': 'application/json',
    'User-Agent': 'nti.webhooks...'}
   >>> print(attempt.request.body)
   "Bob"
   >>> tx.finish()

Because of the way the mock HTTP responses were set up, the
static/global subscription delivery failed.

.. doctest::

   >>> attempt = global_subscription.pop()
   >>> print(attempt.status)
   failed
   >>> print(attempt.message)
   404 Not Found
   >>> attempt.response.status_code
   404
   >>> print(attempt.request.url)
   https://example.com/another/path
   >>> print(attempt.request.method)
   POST
   >>> import pprint
   >>> pprint.pprint({str(k): str(v) for k, v in attempt.request.headers.items()})
   {'Accept': '*/*',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Content-Length': '5',
    'Content-Type': 'application/json',
    'User-Agent': 'nti.webhooks...'}
   >>> print(attempt.request.body)
   "Bob"
   >>> len(attempt.internal_info.exception_history)
   0



.. testcleanup::

   from nti.webhooks.tests.test_docs import zodbTearDown
   zodbTearDown()
