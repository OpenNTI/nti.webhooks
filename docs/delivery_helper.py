import transaction
from zope import lifecycleevent
from zope import interface
from zope.container.folder import Folder
from zope.securitypolicy.interfaces import IPrincipalPermissionManager
from zope.annotation.interfaces import IAttributeAnnotatable

from nti.testing.time import time_monotonically_increases

from nti.webhooks.testing import wait_for_deliveries

__all__ = [
    'deliver_some',
    'wait_for_deliveries',
]

@time_monotonically_increases
def deliver_some(how_many=1, note=None, grants=None, event='created'):
    for _ in range(how_many):
        tx = transaction.begin()
        if note:
            tx.note(note)
        content = Folder()
        if grants:
            # Make sure we can use the default (annotatable)
            # permission managers.
            interface.alsoProvides(content, IAttributeAnnotatable)
            prin_perm = IPrincipalPermissionManager(content)
            for principal_id, perm_id in grants.items():
                prin_perm.grantPermissionToPrincipal(perm_id, principal_id)
        sender = getattr(lifecycleevent, event)
        sender(content)
        transaction.commit()
