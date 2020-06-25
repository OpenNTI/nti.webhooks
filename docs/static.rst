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

.. _z3c.baseregistry: https://github.com/zopefoundation/z3c.baseregistry/tree/master/src/z3c/baseregistry
