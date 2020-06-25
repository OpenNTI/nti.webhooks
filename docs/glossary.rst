.. _glossary:

==========
 Glossary
==========

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

      .. seealso:: :class:`~.IWebhookSubscription`
