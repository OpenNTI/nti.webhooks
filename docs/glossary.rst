.. _glossary:

==========
 Glossary
==========

.. currentmodule:: nti.webhooks.interfaces

.. glossary::
   :sorted:


   subscription
      A target to which webhooks will be delivered.

      Subscriptions may be either :term:`active` or :term:`inactive`.
      Only active subscriptions will result in delivery attempts.

      In addition to capturing the target URL and HTTP method to use,
      a subscription knows the :term:`dialect` to use, along with the
      security restrictions to apply. It also has a :term:`delivery
      history`.

      .. seealso:: :class:`IWebhookSubscription`

   trigger
      An :class:`zope.interface.interfaces.IObjectEvent`, when
      notified through :func:`zope.event.notify` may trigger a
      matching subscription to attempt a delivery.

   active
      Of a subscription: An existing subscription is active if it
      is ready to accept webhook deliveries. Contrast with
      :term:`inactive`. A subscription in this state may transaction
      to inactive at any time.

   inactive
      Of a subscription: An existing subscription is inactive if
      webhook deliviries will no longer be attempted to it. It may
      transition back to :term:`active` at any time.

   applicable
      Of a subscription: Does the subscription apply to some piece of
      data, including permission checks? Only active subscriptions
      should be applicable.

   dialect
      A customization point for a subscription. A dialect is
      used to create and populate the HTTP request.

      .. seealso:: :class:`IWebhookDialect` and :class:`nti.webhooks.dialect.DefaultWebhookDialect`

   target
      Of a subscription: The URL to which the HTTP request is sent.

   externalized
      Of an object: Written out in a format suitable for use in an
      HTTP REST API, such as JSON, using :mod:`nti.externalization`.
