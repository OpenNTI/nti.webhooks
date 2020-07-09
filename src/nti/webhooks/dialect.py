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

from nti import externalization
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

    #: The name of the externalizer used to produce the
    #: external form. This is also the highest-priority name
    #: of the adapter used.
    externalizer_name = u'webhook-delivery'

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
        payload = self.produce_payload(data, event)
        ext_data = externalization.to_external_representation(
            payload,
            ext_format=self.externalizer_format,
            name=self.externalizer_name)
        return ext_data
