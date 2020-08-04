# -*- coding: utf-8 -*-
"""
Implementations of dialects.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import pkg_resources
from zope.interface import implementer
from zope import component

from requests import Request

from nti import externalization
from nti.externalization.interfaces import IExternalObjectRepresenter
from nti.webhooks.interfaces import IWebhookDialect
from nti.webhooks.interfaces import IWebhookPayload

@implementer(IWebhookDialect)
class DefaultWebhookDialect(object):
    """
    Default implementation of a
    :class:`nti.webhooks.interfaces.IWebhookDialect`.

    This class is intended to be subclassed; other dialect
    implementations *should* extend this class. This permits freedom
    in adding additional methods to the interface.
    """

    # REMEMBER: Keep the ZCML directive in sync with
    # this as much as possible.

    #: The name of the externalizer used to produce the
    #: external form. This is also the highest-priority name
    #: of the adapter used.
    externalizer_name = u'webhook-delivery'

    #: The name of the externalization policy utility
    #: used to produce the external form. This defaults to one
    #: that uses ISO8601 format for Unix timestamps.
    externalizer_policy_name = u'webhook-delivery'

    #: Which representation to use. Passed to
    #: :func:`nti.externaliaztion.to_external_representation`
    externalizer_format = externalization.representation.EXT_REPR_JSON

    #: The MIME type of the body produced by :meth:`externalizeData`.
    #: If you change the :attr:`externalizer_format`, you need to change
    #: this value.
    content_type = 'application/json'

    #: The HTTP "User-Agent" header.
    user_agent = 'nti.webhooks %s' % (
        pkg_resources.require('nti.webhooks')[0].version,
    )

    #: The HTTP method (verb) to use.
    http_method = 'POST'

    def produce_payload(self, data, event):
        """
        produce_payload(data, event) -> IWebhookPayload

        Non-interface method. Given data delivered through an event,
        try to find a ``IWebhookPayload`` for it. From highest to lowest priority,
        this means:

        - A multi-adapter from the object and the event named :attr:`externalizer_name`.
        - The unnamed multi-adapter.
        - A single adapter from the object named :attr:`externalizer_name`
        - The unnamed single adapter.

        The *data* is used as the context for the lookup in all cases.
        XXX: Or maybe we should use the subscription as the context?

        Note that if there exists an adapter registration that
        returns None, we continue with lower-priority adapters.
        """
        result = component.queryMultiAdapter((data, event), IWebhookPayload,
                                             name=self.externalizer_name, context=data)
        if result is not None:
            return result

        result = component.queryMultiAdapter((data, event), IWebhookPayload,
                                             context=data)
        if result is not None:
            return result

        if IWebhookPayload.providedBy(data):
            return data

        result = component.queryAdapter(data, IWebhookPayload,
                                        name=self.externalizer_name, context=data)
        if result is not None:
            return result
        return component.queryAdapter(data, IWebhookPayload, default=data, context=data)

    def externalizeData(self, data, event):
        "See :meth:`nti.webhooks.interfaces.IWebhookDialect.externalizeData`"
        payload = self.produce_payload(data, event)
        # ext_data = externalization.to_external_representation(
        #     payload,
        #     ext_format=self.externalizer_format,
        #     name=self.externalizer_name)
        # ``to_external_representation`` doesn't accept the policy or policy_name
        # argument in nti.externalization 2.0
        policy_name = self.externalizer_policy_name
        if policy_name is None:
            # We do this here to keep clients from knowing the
            # ugly details.
            from nti.externalization._base_interfaces import NotGiven
            policy_name = NotGiven
        ext = externalization.to_external_object(
            payload,
            name=self.externalizer_name,
            policy_name=policy_name)
        rep = component.getUtility(IExternalObjectRepresenter,
                                   name=self.externalizer_format)
        return rep.dump(ext)

    def produce_headers(self, http_session, subscription, attempt):
        headers = {
            'Content-Type': self.content_type,
            'User-Agent': self.user_agent
        }
        return headers

    def prepareRequest(self, http_session, subscription, attempt):
        "See :meth:`nti.webhooks.interfaces.IWebhookDialect.prepareRequest`"
        headers = self.produce_headers(http_session, subscription, attempt)
        http_request = Request(self.http_method, subscription.to,
                               headers=headers,
                               data=attempt.payload_data)
        return http_session.prepare_request(http_request)
