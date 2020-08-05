# Copyright 2020 NextThought
# Released under the terms of the LICENSE file.
import codecs
from setuptools import setup, find_packages


version = '0.0.1'

entry_points = {
}

TESTS_REQUIRE = [
    'coverage',
    'nti.testing',
    'fudge',
    'zope.testrunner',
    'zope.lifecycleevent',
    'zope.securitypolicy', # ZCML directives for granting/denying
    # Easy mocking of ``requests``.
    'responses',
    # Simpler site setup than nti.site
    'zope.app.appsetup',
]

def _read(fname):
    with codecs.open(fname, encoding='utf-8') as f:
        return f.read()

setup(
    name='nti.webhooks',
    version=version,
    author='Jason Madden',
    author_email='jason@nextthought.com',
    description="Python/Zope3 server-side webhooks implementation using ZODB and requests.",
    long_description=_read('README.rst') + '\n\n' + _read('CHANGES.rst'),
    license='Apache',
    keywords='webhook server event zope ZODB',
    url='https://github.com/NextThought/nti.webhooks',
    project_urls={
        'Documentation': 'https://ntiwebhooks.readthedocs.io/en/latest/',
    },
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Framework :: Zope3',
        'Development Status :: 1 - Planning',
    ],
    zip_safe=False,
    packages=find_packages('src'),
    package_dir={'': 'src'},
    namespace_packages=['nti'],
    install_requires=[
        # backport of concurrent.futures; implements the 3.7
        # interface.
        'futures; python_version == "2.7"',
        'zope.authentication', # IAuthentication
        'zope.annotation', # IAttributeAnnotatable
        'zope.interface >= 5.1',
        'zope.container',
        'zope.security', # IPrincipal, Permission
        'zope.principalregistry', # TextId
        'zope.componentvocabulary',
        'zope.vocabularyregistry',
        'zope.securitypolicy', # IPrincipalPermissionManager
        'zope.generations', # schema installers
        'zope.site',
        'nti.site >= 2.2.0',
        'nti.zodb',
        # Consistent interface resolution order in 2.0;
        # externalization policies in 2.1.
        'nti.externalization >= 2.1.0',
        'nti.schema',
        'setuptools',
        'transaction',
    ],
    entry_points=entry_points,
    include_package_data=True,
    extras_require={
        'test': TESTS_REQUIRE,
        'docs': [
            'Sphinx',
            'sphinx_rtd_theme',
            'repoze.sphinx.autointerface',
        ] + TESTS_REQUIRE,
    },
)
