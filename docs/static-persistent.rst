====================================================
 Configured Local, Persistent Webhook Subscriptions
====================================================

.. currentmodule:: nti.webhooks.zcml

.. testsetup::

   from nti.webhooks.tests.test_docs import zodbSetUp
   zodbSetUp()

A step between :doc:`global, static, transient subscriptions
<static>` and :doc:`local, runtime-installed history-preserving
subscriptions <dynamic>` are the subscriptions described in this
document: they are statically configured using ZCML, but instead of
being global, they are located in the database (in a site manager) and
store history.

The ZCML directive is very similar to :class:`IStaticSubscriptionDirective`.

.. autointerface:: IStaticPersistentSubscriptionDirective
   :noindex:

In order to use this directive, there must be at least one site manager
configured in the main ZODB database. This can be done in a variety of
ways, but one of the easiest is to use `zope.app.appsetup
<https://pypi.org/project/zope.app.appsetup/>`_. We do this by just
including its configuration (along with a few standard packages).

.. doctest::

   >>> from zope.configuration import xmlconfig
   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <include package="nti.webhooks" />
   ...   <include package="nti.webhooks" file="subscribers_promiscuous.zcml" />
   ...   <include package="zope.app.appsetup" />
   ... </configure>
   ... """)

Wait, didn't we forget someting? Where's the database? Well, we
haven't established one yet. Let's do that.

.. doctest::

   >>> from nti.site.testing import print_tree
   >>> from nti.webhooks.testing import DoctestTransaction
   >>> tx = DoctestTransaction()
   >>> db = tx.db
   >>> conn = tx.begin()
   >>> root = conn.root()
   >>> print_tree(root, depth=0, details=('len',))
   <Connection Root Dictionary> len=0
   >>> tx.finish()

Of course, creating the database by itself does nothing. Like most
things, ``zope.app.appsetup`` is based on events. Including its
configuration just established the event handlers. In this case, the
event that needs to be sent is
:class:`zope.processlifetime.DatabaseOpened`.

.. doctest::

   >>> from zope.processlifetime import DatabaseOpened
   >>> from zope.event import notify
   >>> notify(DatabaseOpened(db))
   >>> def show_trees():
   ...   def extra_details(obj):
   ...       from nti.webhooks.interfaces import IWebhookSubscription
   ...       if IWebhookSubscription.providedBy(obj):
   ...          return ['to=%s' % (obj.to,), 'active=%s' % (obj.active,)]
   ...       return ()
   ...   with tx as conn:
   ...     root = conn.root()
   ...     print_tree(root,
   ...                depth=0,
   ...                show_unknown=type,
   ...                details=('len', 'siteManager'),
   ...                extra_details=extra_details,
   ...                basic_indent='  ',
   ...                known_types=(int, tuple,))
   >>> show_trees()
   <Connection Root Dictionary> len=1
      <ISite,IRootFolder>: Application len=0
        <Site Manager> name=++etc++site len=1
          default len=3
            CookieClientIdManager => <class 'zope.session.http.CookieClientIdManager'>
            PersistentSessionDataContainer len=0
            RootErrorReportingUtility => <class 'zope.error.error.RootErrorReportingUtility'>


The event handler here first made sure there was a site (called
"Application") with a few standard utilities, and then notified
:class:`zope.processlifetime.DatabaseOpenedWithRoot`. That event is
used by `zope.generations
<https://pypi.org/project/zope.generations/>`_ to perform further
installation activities, as wall as upgrades and migrations.

And finally, then, that's here this package comes in. It connects with
``zope.generations`` to manage adding, and removing, these persistent
local subscriptions.


Adding A Subscription
=====================

Let's use the ZCML to add a subscription. The unique required
parameter here is ``site_path``, which must be the traversable path to
a ``ISite`` into which the persistent subscription manager will be
installed.

.. important::

   To use ``zope.generations``, and consequently this package's
   integration with it, you must either specifically include the
   ``subscriber.zcml`` from that package (which evolves to the minimum
   required generation), or manually register the alternate handler
   that evolves to the maximum available generation.

   If you manually register the alternate subscriber that simply
   checks whether the generation is sufficient, you will not be able
   to make future changes to your persistent webhook subscriptions.

.. doctest::

   >>> zcml_string = """
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <include package="nti.webhooks" file="meta.zcml" />
   ...   <include package="zope.generations" file="subscriber.zcml" />
   ...   <webhooks:persistentSubscription
   ...             site_path="/Application"
   ...             for="zope.container.interfaces.IContentContainer"
   ...             when="zope.lifecycleevent.interfaces.IObjectModifiedEvent"
   ...             to="https://example.com" />
   ... </configure>
   ... """
   >>> _ = xmlconfig.string(zcml_string)


Once again, this hasn't done anything to the database yet, it's merely
collected the necessary information.

.. doctest::

   >>> show_trees()
   <Connection Root Dictionary> len=1
      <ISite,IRootFolder>: Application len=0
        <Site Manager> name=++etc++site len=1
          default len=3
            CookieClientIdManager => <class 'zope.session.http.CookieClientIdManager'>
            PersistentSessionDataContainer len=0
            RootErrorReportingUtility => <class 'zope.error.error.RootErrorReportingUtility'>

To take action we need to notify the event. When we do, we
see that a subscription manager and subscription have been created in
the defined location. Also, some bookkeeping information has been
added to the root of the database.

.. doctest::

   >>> notify(DatabaseOpened(db))
   >>> show_trees()
   <Connection Root Dictionary> len=3
      <ISite,IRootFolder>: Application len=0
        <Site Manager> name=++etc++site len=1
          default len=4
            CookieClientIdManager => <class 'zope.session.http.CookieClientIdManager'>
            PersistentSessionDataContainer len=0
            RootErrorReportingUtility => <class 'zope.error.error.RootErrorReportingUtility'>
            ZCMLWebhookSubscriptionManager len=1
              PersistentSubscription len=0 to=https://example.com active=True
      nti.webhooks.generations.PersistentWebhookSchemaManager => <class 'nti.webhooks.generations.State'>
      zope.generations len=1
        zzzz-nti.webhooks => 1

The bookkeeping information is used to make sure that subscriptions in
the database stay in sync with what's in the ZCML. If we execute the
same ZCML again and re-notify the database opening, nothing in the database changes.

.. doctest::

   >>> _ = xmlconfig.string(zcml_string)
   >>> notify(DatabaseOpened(db))
   >>> show_trees()
   <Connection Root Dictionary> len=3
      <ISite,IRootFolder>: Application len=0
        <Site Manager> name=++etc++site len=1
          default len=4
            CookieClientIdManager => <class 'zope.session.http.CookieClientIdManager'>
            PersistentSessionDataContainer len=0
            RootErrorReportingUtility => <class 'zope.error.error.RootErrorReportingUtility'>
            ZCMLWebhookSubscriptionManager len=1
              PersistentSubscription len=0 to=https://example.com active=True
      nti.webhooks.generations.PersistentWebhookSchemaManager => <class 'nti.webhooks.generations.State'>
      zope.generations len=1
        zzzz-nti.webhooks => 1


Delivering To The Subscription
==============================

Delivering to the subscription can happen in two ways. We'll use the same helper function
in both examples.

.. doctest::

   >>> from nti.testing.time import time_monotonically_increases
   >>> from nti.webhooks.testing import wait_for_deliveries
   >>> from zope.container.folder import Folder
   >>> from zope import lifecycleevent
   >>> @time_monotonically_increases
   ... def deliver_one(content=None):
   ...       content = Folder() if content is None else content
   ...       lifecycleevent.modified(content)
   >>> from nti.webhooks.testing import mock_delivery_to
   >>> mock_delivery_to('https://example.com', method='POST', status=200)

.. rubric:: The Site Is The Active Site

First, if that site is the current active site, a matching resource
and event will trigger delivery.

.. doctest::

   >>> from zope.traversing import api as ztapi
   >>> from zope.component.hooks import site as active_site
   >>> with tx as conn:
   ...     site = conn.root.Application
   ...     with active_site(site):
   ...         deliver_one()
   >>> wait_for_deliveries()
   >>> show_trees()
   <Connection Root Dictionary> len=3
      <ISite,IRootFolder>: Application len=0
        <Site Manager> name=++etc++site len=1
          default len=4
            CookieClientIdManager => <class 'zope.session.http.CookieClientIdManager'>
            PersistentSessionDataContainer len=0
            RootErrorReportingUtility => <class 'zope.error.error.RootErrorReportingUtility'>
            ZCMLWebhookSubscriptionManager len=1
              PersistentSubscription len=1 to=https://example.com active=True
                ... => <class 'nti.webhooks.attempts.PersistentWebhookDeliveryAttempt'>
      nti.webhooks.generations.PersistentWebhookSchemaManager => <class 'nti.webhooks.generations.State'>
      zope.generations len=1
        zzzz-nti.webhooks => 1

Note how the ``PersistentSubscription`` has gained a delivery attempt.

.. rubric:: In The Context Of The Site

Second, if something were to happen to an object within the context
(beneath) that site, then, no matter what the active site is, delivery will
be attempted.

.. doctest::

   >>> from zope import component
   >>> with tx as conn:
   ...    site = conn.root.Application
   ...    assert component.getSiteManager() is component.getGlobalSiteManager()
   ...    site['Folder'] = Folder()
   ...    deliver_one(site['Folder'])
   >>> wait_for_deliveries()
   >>> show_trees()
   <Connection Root Dictionary> len=3
      <ISite,IRootFolder>: Application len=1
        Folder len=0
        <Site Manager> name=++etc++site len=1
          default len=4
            CookieClientIdManager => <class 'zope.session.http.CookieClientIdManager'>
            PersistentSessionDataContainer len=0
            RootErrorReportingUtility => <class 'zope.error.error.RootErrorReportingUtility'>
            ZCMLWebhookSubscriptionManager len=1
              PersistentSubscription len=3 to=https://example.com active=True
                ... => <class 'nti.webhooks.attempts.PersistentWebhookDeliveryAttempt'>
                ... => <class 'nti.webhooks.attempts.PersistentWebhookDeliveryAttempt'>
                ... => <class 'nti.webhooks.attempts.PersistentWebhookDeliveryAttempt'>
      nti.webhooks.generations.PersistentWebhookSchemaManager => <class 'nti.webhooks.generations.State'>
      zope.generations len=1
        zzzz-nti.webhooks => 1

The number of delivery attempts has again grown.

.. important::

   But why did it grow by *two* new delivery attempts? We only tried
   to deliver one event.

   The answer is that adding the folder to the site first sent a
   :class:`zope.container.contained.ContainerModifiedEvent` for the
   site folder itself, and then we sent a modified event for the
   folder we just created. The site and its ``ContainerModifiedEvent``
   matched our subscription filter.

   This is a reminder to be careful about the subscription filters or
   the :doc:`configuration` you choose.

.. rubric:: Neither Of The Above

Finally, we'll prove that if the site isn't the current site, and the object being
modified isn't in the context of that site, no delivery is attempted.

.. doctest::

   >>> with tx as conn:
   ...    assert component.getSiteManager() is component.getGlobalSiteManager()
   ...    deliver_one()
   >>> wait_for_deliveries()
   >>> show_trees()
   <Connection Root Dictionary> len=3
      <ISite,IRootFolder>: Application len=1
        Folder len=0
        <Site Manager> name=++etc++site len=1
          default len=4
            CookieClientIdManager => <class 'zope.session.http.CookieClientIdManager'>
            PersistentSessionDataContainer len=0
            RootErrorReportingUtility => <class 'zope.error.error.RootErrorReportingUtility'>
            ZCMLWebhookSubscriptionManager len=1
              PersistentSubscription len=3 to=https://example.com active=True
                ... => <class 'nti.webhooks.attempts.PersistentWebhookDeliveryAttempt'>
                ... => <class 'nti.webhooks.attempts.PersistentWebhookDeliveryAttempt'>
                ... => <class 'nti.webhooks.attempts.PersistentWebhookDeliveryAttempt'>
      nti.webhooks.generations.PersistentWebhookSchemaManager => <class 'nti.webhooks.generations.State'>
      zope.generations len=1
        zzzz-nti.webhooks => 1

As we can see, nothing changed.


Mutating Subscriptions
======================

Over time, the ZCHL configuration is likely to change. Subscriptions
will be added, removed, or (in rare cases) updated.

.. tip::

   Note that subscriptions are identified by their parameters in the
   ZCML. Changing any of those parameters counts as a new
   subscription and a deactivation of the old subscription.

When that happens, the schema manager will make the appropriate
adjustments. For additions, a new subscription will be created;
existing subscriptions will be unchanged.

.. doctest::

   >>> zcml_string = """
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <include package="nti.webhooks" file="meta.zcml" />
   ...   <include package="zope.generations" file="subscriber.zcml" />
   ...   <webhooks:persistentSubscription
   ...             site_path="/Application"
   ...             for="zope.container.interfaces.IContentContainer"
   ...             when="zope.lifecycleevent.interfaces.IObjectModifiedEvent"
   ...             to="https://example.com" />
   ...   <webhooks:persistentSubscription
   ...             site_path="/Application"
   ...             for="zope.container.interfaces.IContentContainer"
   ...             when="zope.lifecycleevent.interfaces.IObjectModifiedEvent"
   ...             to="https://example.com/another/path" />
   ... </configure>
   ... """
   >>> _ = xmlconfig.string(zcml_string)
   >>> notify(DatabaseOpened(db))
   >>> show_trees()
   <Connection Root Dictionary> len=3
      <ISite,IRootFolder>: Application len=1
        Folder len=0
        <Site Manager> name=++etc++site len=1
          default len=4
            CookieClientIdManager => <class 'zope.session.http.CookieClientIdManager'>
            PersistentSessionDataContainer len=0
            RootErrorReportingUtility => <class 'zope.error.error.RootErrorReportingUtility'>
            ZCMLWebhookSubscriptionManager len=2
              PersistentSubscription len=3 to=https://example.com active=True
                ... => <class 'nti.webhooks.attempts.PersistentWebhookDeliveryAttempt'>
                ... => <class 'nti.webhooks.attempts.PersistentWebhookDeliveryAttempt'>
                ... => <class 'nti.webhooks.attempts.PersistentWebhookDeliveryAttempt'>
              PersistentSubscription-2 len=0 to=https://example.com/another/path active=True
      nti.webhooks.generations.PersistentWebhookSchemaManager => <class 'nti.webhooks.generations.State'>
      zope.generations len=1
        zzzz-nti.webhooks => 2

Notice the addition of a new subscription, and the increment of the generation.

Now we'll try something a bit more complex. We'll add a new
subscription *above* the existing subscriptions, "mutate" one of the
existing subscriptions, and completely remove one by commenting it
out.

.. doctest::

   >>> zcml_string = """
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <include package="nti.webhooks" file="meta.zcml" />
   ...   <include package="zope.generations" file="subscriber.zcml" />
   ...   <webhooks:persistentSubscription
   ...             site_path="/Application"
   ...             for="zope.container.interfaces.IContentContainer"
   ...             when="zope.lifecycleevent.interfaces.IObjectModifiedEvent"
   ...             to="https://example.com/ThisIsNew" />
   ...   <!-- Comment out this one
   ...   <webhooks:persistentSubscription
   ...             site_path="/Application"
   ...             for="zope.container.interfaces.IContentContainer"
   ...             when="zope.lifecycleevent.interfaces.IObjectModifiedEvent"
   ...             to="https://example.com" />
   ...   -->
   ...   <webhooks:persistentSubscription
   ...             site_path="/Application"
   ...             for="zope.container.interfaces.IContentContainer"
   ...             when="zope.lifecycleevent.interfaces.IObjectModifiedEvent"
   ...             to="https://example.com/another/path" />
   ... </configure>
   ... """
   >>> _ = xmlconfig.string(zcml_string)
   >>> notify(DatabaseOpened(db))
   >>> show_trees()
   <Connection Root Dictionary> len=3
      <ISite,IRootFolder>: Application len=1
        Folder len=0
        <Site Manager> name=++etc++site len=1
          default len=4
            CookieClientIdManager => <class 'zope.session.http.CookieClientIdManager'>
            PersistentSessionDataContainer len=0
            RootErrorReportingUtility => <class 'zope.error.error.RootErrorReportingUtility'>
            ZCMLWebhookSubscriptionManager len=3
              PersistentSubscription len=3 to=https://example.com active=False
                ... => <class 'nti.webhooks.attempts.PersistentWebhookDeliveryAttempt'>
                ... => <class 'nti.webhooks.attempts.PersistentWebhookDeliveryAttempt'>
                ... => <class 'nti.webhooks.attempts.PersistentWebhookDeliveryAttempt'>
              PersistentSubscription-2 len=0 to=https://example.com/another/path active=True
              PersistentSubscription-3 len=0 to=https://example.com/ThisIsNew active=True
      nti.webhooks.generations.PersistentWebhookSchemaManager => <class 'nti.webhooks.generations.State'>
      zope.generations len=1
        zzzz-nti.webhooks => 3

We can see the addition of a new subscription. The one we deleted is
still present in the database, but in fact it was deactivated. What happens if we
uncomment it?

   >>> zcml_string = """
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <include package="nti.webhooks" file="meta.zcml" />
   ...   <include package="zope.generations" file="subscriber.zcml" />
   ...   <webhooks:persistentSubscription
   ...             site_path="/Application"
   ...             for="zope.container.interfaces.IContentContainer"
   ...             when="zope.lifecycleevent.interfaces.IObjectModifiedEvent"
   ...             to="https://example.com/ThisIsNew" />
   ...   <webhooks:persistentSubscription
   ...             site_path="/Application"
   ...             for="zope.container.interfaces.IContentContainer"
   ...             when="zope.lifecycleevent.interfaces.IObjectModifiedEvent"
   ...             to="https://example.com" />
   ...   <webhooks:persistentSubscription
   ...             site_path="/Application"
   ...             for="zope.container.interfaces.IContentContainer"
   ...             when="zope.lifecycleevent.interfaces.IObjectModifiedEvent"
   ...             to="https://example.com/another/path" />
   ... </configure>
   ... """
   >>> _ = xmlconfig.string(zcml_string)
   >>> notify(DatabaseOpened(db))
   >>> show_trees()
   <Connection Root Dictionary> len=3
      <ISite,IRootFolder>: Application len=1
        Folder len=0
        <Site Manager> name=++etc++site len=1
          default len=4
            CookieClientIdManager => <class 'zope.session.http.CookieClientIdManager'>
            PersistentSessionDataContainer len=0
            RootErrorReportingUtility => <class 'zope.error.error.RootErrorReportingUtility'>
            ZCMLWebhookSubscriptionManager len=4
              PersistentSubscription len=3 to=https://example.com active=False
                ... => <class 'nti.webhooks.attempts.PersistentWebhookDeliveryAttempt'>
                ... => <class 'nti.webhooks.attempts.PersistentWebhookDeliveryAttempt'>
                ... => <class 'nti.webhooks.attempts.PersistentWebhookDeliveryAttempt'>
              PersistentSubscription-2 len=0 to=https://example.com/another/path active=True
              PersistentSubscription-3 len=0 to=https://example.com/ThisIsNew active=True
              PersistentSubscription-4 len=0 to=https://example.com active=True
      nti.webhooks.generations.PersistentWebhookSchemaManager => <class 'nti.webhooks.generations.State'>
      zope.generations len=1
        zzzz-nti.webhooks => 4

A new subscription is added. No attempt is made to re-activate a
previously existing deactivated subscription.

.. testcleanup::

   from nti.webhooks.tests.test_docs import zodbTearDown
   zodbTearDown()
