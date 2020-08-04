# -*- coding: utf-8 -*-
"""
Externalization support.

This includes helpers for the objects defined in this
package, as well as general helpers for other packages.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from nti.externalization import to_external_object
from nti.externalization.interfaces import ExternalizationPolicy
from nti.externalization.datastructures import InterfaceObjectIO

from nti.webhooks.interfaces import IWebhookSubscription
from nti.webhooks.interfaces import IWebhookDeliveryAttempt
from nti.webhooks.interfaces import IWebhookDeliveryAttemptRequest
from nti.webhooks.interfaces import IWebhookDeliveryAttemptResponse

from nti.webhooks._util import describe_class_or_specification

__all__ = [
    'ISODateExternalizationPolicy',
]

#: An externalization policy that uses ISO 8601 date strings.
ISODateExternalizationPolicy = ExternalizationPolicy(
    use_iso8601_for_unix_timestamp=True
)

class SubscriptionExternalizer(InterfaceObjectIO):
    _ext_iface_upper_bound = IWebhookSubscription

    _excluded_out_ivars_ = frozenset({
        # Dialect_id is better than dialect.
        'dialect',
        # for_ and when are arbitrary classes or interface
        # specifications. They're not meaningful to end users by themselves.
        'for_', 'when',
        # Redundant IDCTimes data
        'created', 'modified',
    }) | InterfaceObjectIO._excluded_out_ivars_

    def toExternalObject(self, *args, **kwargs): # pylint:disable=signature-differs
        result = super(SubscriptionExternalizer, self).toExternalObject(*args, **kwargs)
        context = self._ext_self
        result['Contents'] = to_external_object(list(context.values()))
        # TODO: This is a temporary hack. We need to figure out if there is anything
        # useful for receivers to have here or if its better just to omit it.
        result['for_'] = describe_class_or_specification(context.for_)
        result['when'] = describe_class_or_specification(context.when)
        return result

class DeliveryAttemptExternalizer(InterfaceObjectIO):
    _ext_iface_upper_bound = IWebhookDeliveryAttempt

    _excluded_out_ivars_ = frozenset({
        # This is...internal. Duh.
        'internal_info',
        # Redundant IDCTimes data
        'created', 'modified',
    }) | InterfaceObjectIO._excluded_out_ivars_


class DeliveryAttemptRequestExternalizer(InterfaceObjectIO):
    _ext_iface_upper_bound = IWebhookDeliveryAttemptRequest

    _excluded_out_ivars_ = frozenset({
        # Redundant IDCTimes data
        'created', 'modified',
    }) | InterfaceObjectIO._excluded_out_ivars_

class DeliveryAttemptResponseExternalizer(InterfaceObjectIO):
    _ext_iface_upper_bound = IWebhookDeliveryAttemptResponse

    _excluded_out_ivars_ = frozenset({
        # Redundant IDCTimes data
        'created', 'modified',
    }) | InterfaceObjectIO._excluded_out_ivars_
