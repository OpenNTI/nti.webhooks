====================================================
 Configured Local, Persistent Webhook Subscriptions
====================================================

.. currentmodule:: nti.webhooks.zcml

.. testsetup::

   from zope.testing import cleanup
   # zope.session is not strict-iro friendly at this time
   from zope.interface import ro
   ro.C3.STRICT_IRO = False
   # We don't establish the securitypolicy, so zope.app.appsetup
   # complains by logging. Silence that.
   import logging
   logging.getLogger('zope.app.appsetup').setLevel(logging.CRITICAL)

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
   >>> print_tree(root, depth=0, details=('len',))
   <Connection Root Dictionary> len=0
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
   ...     print_tree(root,
   ...                depth=0,
   ...                show_unknown=type,
   ...                details=('len', 'siteManager'),
   ...                basic_indent='  ',
   ...                known_types=(int, tuple,))
   ...     conn.close()
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
   ...             when="zope.lifecycleevent.interfaces.IObjectCreatedEvent"
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
            WebhookSubscriptionManager len=1
              PersistentSubscription len=0
      nti.webhooks.generations.PersistentWebhookSchemaManager len=2 => ((('/Application',...
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
            WebhookSubscriptionManager len=1
              PersistentSubscription len=0
      nti.webhooks.generations.PersistentWebhookSchemaManager len=2 => ((('/Application',...
      zope.generations len=1
        zzzz-nti.webhooks => 1


.. todo:: Deliver to the subscription, both with and without the site active.
.. todo:: Add a new subscription, verify the old subscription is unchanged.
.. todo:: Mutate one of the definitions, verify that a new subscription is created while the old
          one is deactivated.
.. todo:: Likewise for removing a definition.

.. testcleanup::

   from zope.testing import cleanup
   cleanup.cleanUp()
   ro.C3.STRICT_IRO = ro._ClassBoolFromEnv()
   db.close()
