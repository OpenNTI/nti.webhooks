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
from nti.externalization.interfaces import StandardExternalFields
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

MIMETYPE = StandardExternalFields.MIMETYPE

class _MimeTypeInsertingExternalizer(InterfaceObjectIO):
    # Normally, AutoPackageSearchingScopedInterfaceObjectIO would add
    # mimeType fields to the classes it is registered for. But that only happens
    # when we use the ``<ext:registerAutoPackageIO>`` ZCML directive,
    # which we don't do here.
    #
    # Instead, we ask subclasses to define the mimetype they want to use.
    _WH_EXTERNAL_MIME_TYPE = None

    _excluded_out_ivars_ = frozenset({
        # Redundant IDCTimes data
        'created', 'modified',
    }) | InterfaceObjectIO._excluded_out_ivars_

    @classmethod
    def mimeTypeFromInterface(cls, iface):
        # TODO: On Python 3, we could use the
        # subclass init hook to set this automatically without
        # needing a meta class.
        iface_name = iface.__name__
        assert iface_name[0] == 'I'
        iface_name = iface_name[1:].lower()

        return 'application/vnd.nextthought.webhooks.' + iface_name

    def toExternalObject(self, *args, **kwargs): # pylint:disable=signature-differs
        result = super(_MimeTypeInsertingExternalizer, self).toExternalObject(*args, **kwargs)
        if MIMETYPE not in result:
            result[MIMETYPE] = self._WH_EXTERNAL_MIME_TYPE
        return result


class SubscriptionExternalizer(_MimeTypeInsertingExternalizer):
    _ext_iface_upper_bound = IWebhookSubscription

    _WH_EXTERNAL_MIME_TYPE = _MimeTypeInsertingExternalizer.mimeTypeFromInterface(
        _ext_iface_upper_bound
    )

    _excluded_out_ivars_ = frozenset({
        # Dialect_id is better than dialect.
        'dialect',
        # for_ and when are arbitrary classes or interface
        # specifications. They're not meaningful to end users by themselves.
        'for_', 'when',
    }) | _MimeTypeInsertingExternalizer._excluded_out_ivars_

    def toExternalObject(self, *args, **kwargs):
        result = super(SubscriptionExternalizer, self).toExternalObject(*args, **kwargs)
        context = self._ext_self
        result['Contents'] = to_external_object(list(context.values()))
        # TODO: This is a temporary hack. We need to figure out if there is anything
        # useful for receivers to have here or if its better just to omit it.
        result['for_'] = describe_class_or_specification(context.for_)
        result['when'] = describe_class_or_specification(context.when)
        return result


class DeliveryAttemptExternalizer(_MimeTypeInsertingExternalizer):
    _ext_iface_upper_bound = IWebhookDeliveryAttempt
    _WH_EXTERNAL_MIME_TYPE = _MimeTypeInsertingExternalizer.mimeTypeFromInterface(
        _ext_iface_upper_bound
    )

    _excluded_out_ivars_ = frozenset({
        # This is...internal. Duh.
        'internal_info',
    }) | _MimeTypeInsertingExternalizer._excluded_out_ivars_


class DeliveryAttemptRequestExternalizer(_MimeTypeInsertingExternalizer):
    _ext_iface_upper_bound = IWebhookDeliveryAttemptRequest
    _WH_EXTERNAL_MIME_TYPE = _MimeTypeInsertingExternalizer.mimeTypeFromInterface(
        _ext_iface_upper_bound
    )


class DeliveryAttemptResponseExternalizer(_MimeTypeInsertingExternalizer):
    _ext_iface_upper_bound = IWebhookDeliveryAttemptResponse
    _WH_EXTERNAL_MIME_TYPE = _MimeTypeInsertingExternalizer.mimeTypeFromInterface(
        _ext_iface_upper_bound
    )
