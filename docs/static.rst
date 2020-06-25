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
configuration file that defines it:

.. doctest::

   >>> from zope.configuration import xmlconfig
   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...    <include package="nti.webhooks" file="meta.zcml" />
   ... </configure>
   ... """)

Once that's done, we can use the ``webhooks:staticSubscription`` XML
tag to define a subscription to start receiving our webhook
deliveries.

There is only one required argument: the destination URL.

.. doctest::

   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <webhooks:staticSubscription to="https://example.com" />
   ... </configure>
   ... """, conf_context)

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


The above registration will try to send *all* ``IObjectEvent`` events
for *all* objects (that implement an interface) to
``https://example.com`` using the default dialect. That's unlikely to
be what you want, outside of tests. Instead, you'll want to limit the
event to particular kinds of objects, and particular events in their
lifecycle. The ``for`` and ``when`` attributes let you do that. Here,
we'll say that whenever a new :class:`zope.container.interfaces.IContainer`
is created, we'd like to deliver a webhook.

.. doctest::

   >>> conf_context = xmlconfig.string("""
   ... <configure
   ...     xmlns="http://namespaces.zope.org/zope"
   ...     xmlns:webhooks="http://nextthought.com/ntp/webhooks"
   ...     >
   ...   <webhooks:staticSubscription
   ...             to="https://example.com"
   ...             for="zope.container.interfaces.IContainer"
   ...             when="zope.lifecycleevent.interfaces.IObjectCreatedEvent" />
   ... </configure>
   ... """, conf_context)


.. _z3c.baseregistry: https://github.com/zopefoundation/z3c.baseregistry/tree/master/src/z3c/baseregistry
