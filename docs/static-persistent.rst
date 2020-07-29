====================================================
 Configured Local, Persistent Webhook Subscriptions
====================================================

.. currentmodule:: nti.webhooks.zcml

.. testsetup::

   from zope.testing import cleanup
   # zope.session is not strict-iro friendly at this time
   from zope.interface import ro
   ro.C3.STRICT_IRO = False

A step between :doc:`global, static, transient subscriptions
<static>` and :doc:`local, runtime-installed history-free
subscriptions <dynamic>` are the subscriptions described in this
document: they are statically configured using ZCML, but instead of
being global, they are located in the database (in a site manager) and
store history.

The ZCML directive is very similar to :class:`IStaticSubscriptionDirective`.

.. autointerface:: IStaticPersistentSubscriptionDirective


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
   >>> from ZODB import DB, DemoStorage
   >>> db = DB(DemoStorage.DemoStorage())
   >>> conn = db.open()
   >>> root = conn.root()
   >>> print_tree(root)
        <Connection Root Dictionary> ... <class 'persistent.mapping.PersistentMapping'>
   >>> conn.close()

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
   ...     conn = db.open()
   ...     root = conn.root()
   ...     print_tree(root)
   ...     app = conn.root.Application
   ...     site_man = app.getSiteManager()
   ...     print_tree(site_man)
   ...     conn.close()
   >>> show_trees()
        <Connection Root Dictionary> ... <class 'persistent.mapping.PersistentMapping'>
            <ISite,IRootFolder>: Application ... <class 'zope.site.folder.Folder'>
         ++etc++site ... <class 'zope.site.site.LocalSiteManager'>
             default ... <class 'zope.site.site.SiteManagementFolder'>
                 CookieClientIdManager ... <class 'zope.session.http.CookieClientIdManager'>
                     <zope.session.http.CookieClientIdManager ...>
                 PersistentSessionDataContainer ... <class 'zope.session.session.PersistentSessionDataContainer'>
                 RootErrorReportingUtility ... <class 'zope.error.error.RootErrorReportingUtility'>
                     <zope.error.error.RootErrorReportingUtility ...>

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

.. doctest::

   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <include package="nti.webhooks" file="meta.zcml" />
   ...   <webhooks:persistentSubscription
   ...             site_path="/Application"
   ...             to="https://example.com" />
   ... </configure>
   ... """)


This hasn't actually done anything yet, it's merely collected the necessary information.

.. doctest::
   >>> show_trees()
        <Connection Root Dictionary> ... <class 'persistent.mapping.PersistentMapping'>
            <ISite,IRootFolder>: Application ... <class 'zope.site.folder.Folder'>
         ++etc++site ... <class 'zope.site.site.LocalSiteManager'>
             default ... <class 'zope.site.site.SiteManagementFolder'>
                 CookieClientIdManager ... <class 'zope.session.http.CookieClientIdManager'>
                     <zope.session.http.CookieClientIdManager ...>
                 PersistentSessionDataContainer ... <class 'zope.session.session.PersistentSessionDataContainer'>
                 RootErrorReportingUtility ... <class 'zope.error.error.RootErrorReportingUtility'>
                     <zope.error.error.RootErrorReportingUtility ...>

Once again, to take action we need to notify the event.

.. doctest::

   >>> notify(DatabaseOpened(db))
   >>> show_trees()

.. testcleanup::

   from zope.testing import cleanup
   cleanup.cleanUp()
   ro.C3.STRICT_IRO = ro._ClassBoolFromEnv()
   db.close()
