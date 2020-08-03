from persistent import Persistent
from zope.container.contained import Contained
from zope.site.folder import Folder
from zope.site import LocalSiteManager
from zope.annotation.interfaces import IAttributeAnnotatable
from zope.interface import implementer

class Employees(Folder):
    def __init__(self):
        Folder.__init__(self)
        self['employees'] = Folder()
        self.setSiteManager(LocalSiteManager(self))

class Department(Employees):
    pass

class Office(Employees):
    pass

@implementer(IAttributeAnnotatable)
class Employee(Contained, Persistent):
    COUNTER = 0

    def __init__(self):
        self.__counter__ = self.COUNTER
        Employee.COUNTER += 1

    def __repr__(self):
        return "<Employee %s %d>" % (
            self.__name__,
            self.__counter__,
        )

class ExternalizableEmployee(Employee):
    def toExternalObject(self, **kwargs):
        return self.__name__


from zope.testing import cleanup
cleanup.addCleanUp(lambda: setattr(Employee, 'COUNTER', 0))
