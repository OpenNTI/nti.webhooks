=================
 Customizing For
=================

Sometimes the output of :func:`zope.interface.providedBy` is not what
you want the high-level dynamic subscription APIs to use. This can be
customized by providing an adapter for the object to
:class:`nti.webhooks.interfaces.IWebhookResourceDiscriminator`.

Example
=======

Previously in :doc:`../dynamic`, we saw how ``employees.Employee`` got a
very specific registration. Let's add an adapter and see it get a
different registration.

First, we create the normal configuration.

.. doctest::

   >>> from zope.configuration import xmlconfig
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

Next, we create and provide an adapter. When called, it returns the
specific class instead of its set of provided interfaces. Typically,
an adapter will return one specific interface, but it can return
anything that can be passed to
:meth:`zope.interface.interfaces.IComponentRegistry.registerAdapter`
as part of the ``required`` parameter.

.. doctest::

   >>> from zope.interface import implementer
   >>> from zope.component import adapter
   >>> from zope.component import provideAdapter
   >>> from employees import Employee
   >>> from nti.webhooks.interfaces import IWebhookResourceDiscriminator
   >>> @implementer(IWebhookResourceDiscriminator)
   ... @adapter(Employee)
   ... class EmployeeDiscriminator(object):
   ...     def __init__(self, context):
   ...         self.context = context
   ...     def __call__(self):
   ...         return type(self.context)
   >>> provideAdapter(EmployeeDiscriminator)

Now, when we use the high-level API, we find a more specific ``for``
value:


.. doctest::

   >>> from nti.webhooks.api import subscribe_to_resource
   >>> bob = Employee()
   >>> subscription = subscribe_to_resource(bob, 'https://example.com/some/path')
   >>> subscription.for_
   <class 'employees.Employee'>


.. testcleanup::

   from zope.testing import cleanup
   cleanup.cleanUp()
