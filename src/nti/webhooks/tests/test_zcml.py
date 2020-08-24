# -*- coding: utf-8 -*-
"""
Tests for zcml.py and ZCML configuration.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function


from nti.testing import base



class TestConfiguration(base.AbstractTestBase):

    def test_duplicate_permissions_in_zcml_conflict(self, conflict=True):
        # Duplicate permission IDs conflict; this is because
        # the discriminator used by zope.component.zcml just includes
        # ('utility', IPermission, <permission id>).
        # Conflicts can be resolved if the path portion of one item is the
        # subpath of another item (something about hierarchal includes) so
        # to actually test this we have to write *two* files outside our
        # hierarchy and include them both

        from zope.configuration import xmlconfig
        from zope.configuration.config import ConfigurationConflictError
        import tempfile

        if conflict:
            exclude = ''
        else:
            exclude = '<exclude package="nti.webhooks" file="permissions.zcml" />'

        for perm_id in ('nti.actions.create', 'nti.actions.delete'):
            perm_zcml = """
            <configure  xmlns="http://namespaces.zope.org/zope"
                        i18n_domain="nti.somethingelse">
             <include package="zope.security" />
             <permission
               id="%s"
               title="something"/>
            </configure>
            """ % (perm_id,)

            with tempfile.NamedTemporaryFile('wt') as perm_file:
                perm_file.write(perm_zcml)
                perm_file.flush()
                with tempfile.NamedTemporaryFile('wt') as zcml_file:
                    zcml = """
                    <configure  xmlns="http://namespaces.zope.org/zope"
                        i18n_domain="nti.somethingelse">

                      <include package="zope.component" file="meta.zcml" />
                      %s
                      <include package="nti.webhooks" />
                      <include file="%s" />
                    </configure>
                    """ % (exclude, perm_file.name,)
                    zcml_file.write(zcml)
                    zcml_file.flush()

                    if conflict:
                        with self.assertRaises(ConfigurationConflictError):
                            xmlconfig.file(zcml_file.name)
                    else:
                        xmlconfig.file(zcml_file.name)

    def test_duplicate_permissions_in_zcml_excluded(self):
        # Adding the exclude directive *before* processing the file fixes things.
        self.test_duplicate_permissions_in_zcml_conflict(conflict=False)
