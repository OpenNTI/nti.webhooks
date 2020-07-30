# -*- coding: utf-8 -*-
"""
Support for configuring webhook delivery using ZCML.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope.configuration.fields import GlobalObject
from zope.configuration.fields import Text

from zope import component
from zope.interface import Interface

from zope.security.zcml import Permission

from nti.webhooks.subscriptions import getGlobalSubscriptionManager
from nti.webhooks.interfaces import IWebhookSubscription
from nti.webhooks._schema import ObjectEventInterface

# pylint:disable=inherit-non-class

class Path(Text):
    """
    Accepts a single absolute traversable path.

    Unlike :class:`zope.configuration.fields.Path`, this version
    requires that the path be absolute and uses URL separators.
    """

    def fromUnicode(self, value):
        result = super(Path, self).fromUnicode(value)
        if not result or not result.startswith('/'):
            raise ValueError() # XXX: This should be something specific.
        return result


class IStaticSubscriptionDirective(Interface):
    """
    Define a global, static, transient subscription.

    Static subscriptions are not persistent and live only in the
    memory of individual processes. Thus, failed deliveries cannot be
    re-attempted after process shutdown. And of course the delivery history
    is also transient and local to a process.
    """

    for_ = GlobalObject(
        title=IWebhookSubscription['for_'].title,
        description=IWebhookSubscription['for_'].description,
        default=IWebhookSubscription['for_'].default,
        required=False,
    )

    when = ObjectEventInterface(
        title=IWebhookSubscription['when'].title,
        description=IWebhookSubscription['when'].description,
        default=IWebhookSubscription['when'].default,
        required=False,
    )

    to = IWebhookSubscription['to'].bind(None)

    dialect = IWebhookSubscription['dialect_id'].bind(None)

    owner = IWebhookSubscription['owner_id'].bind(None)

    permission = Permission(
        title=u"The permission to check",
        description=u"""
        If given, and an *owner* is also specified, then only data that
        has this permission for the *owner* will result in an attempted delivery.
        If not given, but an *owner* is given, this will default to the standard
        view permission ID, ``zope.View``.
        """,
        required=False
    )


class IStaticPersistentSubscriptionDirective(IStaticSubscriptionDirective):
    """
    Define a local, static, persistent subscription.

    Local persistent subscriptions live in the ZODB database, beneath
    some :class:`zope.site.interfaces.ILocalSiteManager`.

    They are identified by a traversable path beginning from the root
    of the database; note that this may not be the exact same as a
    path exposed in the application because this path will need to
    include the name of the root application object, while application
    paths typically do not.

    This package uses :mod:`zope.generations` to keep track of
    registered subscriptions and synchronize the database with what is
    in executed ZCML. Thus it is very important not to remove ZCML
    directives, or only execute part of the ZCML configuration unless you intend
    for the subscriptions not found in ZCML to be removed.

    All the options are the same as for :class:`IStaticSubscriptionDirective`,
    with the addition of the required ``site_path``.
    """

    site_path = Path(
        title=u'The path to traverse to the site',
        description=u"A persistent subscription manager will be installed in this site.",
        required=True,
    )
    # XXX: Active/inactive. Should be able to keep one without losing the history.

def _static_subscription_action(subscription_kwargs):
    getGlobalSubscriptionManager().createSubscription(**subscription_kwargs)

def _check_sub_kwargs(kwargs):
    to = kwargs.pop('to')
    for_ = kwargs.pop('for_', None) or IStaticSubscriptionDirective['for_'].default
    when = kwargs.pop('when', None) or IStaticSubscriptionDirective['when'].default
    owner = kwargs.pop("owner", None)
    permission = kwargs.pop('permission', None)
    dialect = kwargs.pop('dialect', None)

    if kwargs: # pragma: no cover
        raise TypeError

    subscription_kwargs = dict(to=to,
                               for_=for_,
                               when=when,
                               owner_id=owner,
                               permission_id=permission,
                               dialect_id=dialect)
    return subscription_kwargs

def static_subscription(context, **kwargs):
    # type: (zope.configuration.config.ConfigurationMachine, dict) -> None
    subscription_kwargs = _check_sub_kwargs(kwargs)
    context.action(
        # No conflicts. You can register as many identical hooks
        # as you want.
        discriminator=None,
        callable=_static_subscription_action,
        args=(subscription_kwargs,),
        # Try to execute towards the end so any validation that needs
        # previous directives, like permission lookup, can work.
        order=9999
    )

def _persistent_subscription_action(site_path, subscription_kwargs):
    from .generations import get_schema_manager
    schema = get_schema_manager()
    schema.addSubscription(site_path, subscription_kwargs)

def persistent_subscription(context, site_path=None, **kwargs):
    # We need to add the utility and subscription each time we're invoked
    # in case of z3c.baseregistry, I think. The discriminators should make sure
    # there's only one.

    subscription_kwargs = _check_sub_kwargs(kwargs)

    context.action(
        discriminator=(site_path, tuple(subscription_kwargs.items())),
        callable=_persistent_subscription_action,
        args=(site_path, subscription_kwargs),
    )
