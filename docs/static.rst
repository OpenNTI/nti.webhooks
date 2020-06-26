==============================
 Static Webhook Subscriptions
==============================

.. currentmodule:: nti.webhooks.zcml

The simplest type of webhook :term:`subscription` is one that is
configured statically, typically at application startup time. This
package provides ZCML directives to facilitate this. The directives
can either be used globally, creating subscriptions that are valid
across the entire application, or can be scoped to a smaller portion
of the application using `z3c.baseregistry`_.

.. autointerface:: IStaticSubscriptionDirective


Let's look at an example of how to use this directive from ZCML. We
need to define the XML namespace it's in, and we need to include the
configuration file that defines it. We also need to have the event
dispatching provided by :mod:`zope.component` properly set up, as well
as some other things. Including this package's configuration handles
all of that.

.. doctest::

   >>> from zope.configuration import xmlconfig
   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <include package="nti.webhooks" />
   ... </configure>
   ... """)

Once that's done, we can use the ``webhooks:staticSubscription`` XML
tag to define a subscription to start receiving our webhook
deliveries.

There is only one required argument: the destination URL.

The destination must be HTTPS.

.. doctest::

   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <webhooks:staticSubscription to="http://example.com" />
   ... </configure>
   ... """, conf_context)
   Traceback (most recent call last):
   ...
   zope.configuration.exceptions.ConfigurationError: Invalid value for 'to'
       File "<string>", line 6.2-6.57
       zope.schema.interfaces.InvalidURI: http://example.com


.. doctest::

   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <webhooks:staticSubscription to="https://example.com" />
   ... </configure>
   ... """, conf_context)

.. clean up that registration, we don't actually want it

.. doctest::
   :hide:

   >>> from nti.webhooks.subscriptions import resetGlobals
   >>> resetGlobals()

If we specify a permission to check, it must exist.

.. doctest::

   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <webhooks:staticSubscription
   ...             to="https://example.com"
   ...             permission="no.such.permission" />
   ... </configure>
   ... """, conf_context)
   Traceback (most recent call last):
   ...
   zope.configuration.config.ConfigurationExecutionError: File "<string>", line 6.2-8.46
     Could not read source.
       ValueError: ('Undefined permission ID', 'no.such.permission')


The above (successful) registration will try to send *all* ``IObjectEvent`` events
for all objects that implement :class:`~nti.webhooks.interfaces.IWebhookPayload` to
``https://example.com`` using the default dialect. That's unlikely to
be what you want, outside of tests. Instead, you'll want to limit the
event to particular kinds of objects, and particular events in their
lifecycle. The ``for`` and ``when`` attributes let you do that. Here,
we'll give a comple example saying that whenever a new
:mod:`IContainer <zope.container.interfaces>` is created, we'd like to
deliver a webhook.

.. doctest::

   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <include package="zope.component" />
   ...   <include package="zope.container" />
   ...   <include package="nti.webhooks" file="meta.zcml" />
   ...   <webhooks:staticSubscription
   ...             to="https://example.com"
   ...             for="zope.container.interfaces.IContentContainer"
   ...             when="zope.lifecycleevent.interfaces.IObjectCreatedEvent" />
   ... </configure>
   ... """)

Now that we have that in place, let's verify that it exists and is active:

.. doctest::

   >>> from nti.webhooks.interfaces import IWebhookSubscriptionManager
   >>> from zope import component
   >>> sub_manager = component.getUtility(IWebhookSubscriptionManager)
   >>> list(sub_manager.items())
   [('Subscription', <...Subscription ... {'to': 'https://example.com', 'for_': <InterfaceClass ...IContentContainer>, 'when': <InterfaceClass ...IObjectCreatedEvent>...


..
   Next, we'll create a container and notify that it has been created:

   .. doctest::

      >>> from zope.container.folder import Folder
      >>> lifecycleevent.created(Folder())
      Traceback (most recent call last):
      ...
      zope.interface.interfaces.ComponentLookupError: (<InterfaceClass nti.webhooks.interfaces.IWebhookDeliveryManager>, '')

   Whoops! We need to have a ``IWebhookDeliveryManager`` utility
   available in order for this to work. Loading the configuration of this
   package will provide such a utility (and that's usually the one you
   want), but for the sake of example we'll register our own now:

   .. doctest::

      >>> from zope import interface
      >>> from zope import component
      >>> from nti.webhooks.interfaces import IWebhookDeliveryManager
      >>> @interface.implementer(IWebhookDeliveryManager)
      ... class TestingDeliveryMan(object):
      ...    def temp(self, data, event):
      ...        print("Asked to deliver a hook for", type(data).__name__,
      ...              "from event", type(event).__name__)

      >>> component.provideUtility(TestingDeliveryMan())


   Now we can ask for delivery:

      >>> lifecycleevent.created(Folder())
      Asked to deliver a hook for Folder from event ObjectCreatedEvent

.. _z3c.baseregistry: https://github.com/zopefoundation/z3c.baseregistry/tree/master/src/z3c/baseregistry

.. testcleanup::

   from zope.testing import cleanup
   cleanup.cleanUp()
