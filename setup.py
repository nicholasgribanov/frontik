import sys

from setuptools import setup
from setuptools.command.test import test

from frontik.version import version


class TestHook(test):
    user_options = [('with-coverage', 'c', 'Run test suite with coverage')]

    def initialize_options(self):
        self.with_coverage = False
        test.initialize_options(self)

    def run_tests(self):
        import pytest
        sys.exit(pytest.main(['tests', '--tb', 'native', '--junitxml', 'pytest.xml']))


setup(
    name='frontik',
    version=version,
    description='Frontik is an asyncronous Tornado-based application server',
    long_description=open('README.md').read(),
    url='https://github.com/hhru/frontik',
    cmdclass={
        'test': TestHook
    },
    packages=[
        'frontik', 'frontik/renderers', 'frontik/integrations'
    ],
    package_data={
        'frontik': ['debug/*.xsl'],
    },
    scripts=['scripts/frontik'],
    python_requires='>=3.7',
    install_requires=[
        'jinja2 >= 2.10.1',
        'lxml >= 4.3.3',
        'pycurl >= 7.43.0.2',
        'tornado >= 6.0',
    ],
    test_suite='tests',
    tests_require=[
        'pytest == 4.6.3',
        'pycodestyle == 2.5.0',
        'requests == 2.22.0',
        'lxml-asserts',
        'tornado-httpclient-mock',
    ],
    dependency_links=[
        'https://github.com/hhru/tornado/archive/master.zip',
    ],
    extras_require={
        'sentry': ['sentry-sdk'],
        'kafka': ['aiokafka'],
        'statsd': ['aiostatsd'],
    },
    zip_safe=False
)
