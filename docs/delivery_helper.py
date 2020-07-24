import transaction
from zope import lifecycleevent
from zope import component
from zope import interface
from zope.container.folder import Folder
from zope.securitypolicy.interfaces import IPrincipalPermissionManager
from zope.annotation.interfaces import IAttributeAnnotatable

from nti.testing.time import time_monotonically_increases

from nti.webhooks.interfaces import IWebhookDeliveryManager

@time_monotonically_increases
def deliver_some(how_many=1, note=None, grants=None):
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
        lifecycleevent.created(content)
        transaction.commit()

def wait_for_deliveries():
    delivery_man = component.getUtility(IWebhookDeliveryManager)
    delivery_man.waitForPendingDeliveries()
