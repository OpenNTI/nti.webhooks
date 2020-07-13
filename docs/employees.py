from persistent import Persistent
from zope.container.contained import Contained
from zope.site.folder import Folder
from zope.site import LocalSiteManager

class Employees(Folder):
    def __init__(self):
        Folder.__init__(self)
        self['employees'] = Folder()
        self.setSiteManager(LocalSiteManager(self))

class Department(Employees):
    pass

class Office(Employees):
    pass

class Employee(Contained, Persistent):
    def toExternalObject(self, **kwargs):
        return self.__name__
