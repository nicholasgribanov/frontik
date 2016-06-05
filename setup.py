# coding=utf-8

import os

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.test import test

from frontik import version


class BuildHook(build_py):
    def run(self):
        build_py.run(self)

        build_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.build_lib, 'frontik')
        with open(os.path.join(build_dir, 'version.py'), 'w') as version_file:
            version_file.write('version = "{0}"\n'.format(version))


class TestHook(test):
    user_options = [('with-coverage', 'c', 'Run test suite with coverage')]

    def initialize_options(self):
        self.with_coverage = False
        test.initialize_options(self)

    def run_tests(self):
        import nose
        import logging
        logging.disable(logging.CRITICAL)
        nose.main(argv=['tests', '-v'])

setup(
    name='frontik',
    version=__import__('frontik').__version__,
    description='Frontik is an asyncronous Tornado-based application server',
    long_description=open('README.md').read(),
    url='https://github.com/hhru/frontik',
    cmdclass={
        'build_py': BuildHook,
        'test': TestHook
    },
    packages=[
        'frontik', 'frontik/loggers', 'frontik/producers', 'frontik/server', 'frontik/testing', 'frontik/testing/pages'
    ],
    scripts=['scripts/frontik'],
    package_data={
        'frontik': ['debug/*.xsl'],
    },
    install_requires=[
        'python-daemon',
        'lxml >= 2.3.2',
        'simplejson >= 2.3.2',
        'pycurl >= 7.19.0',
        'jinja2 >= 2.6',
        'tornado >= 3.2.2, < 4',
    ],
    test_suite='tests',
    tests_require=[
        'nose',
        'pep8',
        'requests >= 0.8.2',
    ],
    dependency_links=[
        'https://github.com/hhru/tornado/archive/fix-version.zip',
    ],
    extras_require={
        'futures': ['futures'],
        'sentry': ['raven']
    },
    zip_safe=False
)
