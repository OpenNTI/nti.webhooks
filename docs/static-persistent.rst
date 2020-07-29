====================================================
 Configured Local, Persistent Webhook Subscriptions
====================================================

.. currentmodule:: nti.webhooks.zcml

.. testsetup::

   from zope.testing import cleanup

A step between :doc:`global, static, transient subscriptions
<static>` and :doc:`local, runtime-installed history-free
subscriptions <dynamic>` are the subscriptions described in this
document: they are statically configured using ZCML, but instead of
being global, they are located in the database (in a site manager) and
store history.

The ZCML directive is very similar to :class:`IStaticSubscriptionDirective`.

.. autointerface:: IStaticPersistentSubscriptionDirective


.. testcleanup::

   from zope.testing import cleanup
   cleanup.cleanUp()
