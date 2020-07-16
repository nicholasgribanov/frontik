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
        sys.exit(pytest.main(['tests', '--tb', 'native']))


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
        'frontik', 'frontik/loggers', 'frontik/producers', 'frontik/integrations'
    ],
    package_data={
        'frontik': ['debug/*.xsl'],
    },
    scripts=['scripts/frontik'],
    python_requires='>=3.6',
    install_requires=[
        'jinja2 >= 2.8',
        'lxml >= 3.5.0',
        'pycurl >= 7.43.0',
        'tornado >= 6.0, < 6.0.4',
        'python-consul >= 1.1.0',
        'aiohttp == 3.6.2',
        'balancing-http-client == 1.0.1',
    ],
    test_suite='tests',
    tests_require=[
        'pytest <= 3.8.2',
        'pycodestyle == 2.5.0',
        'requests <= 2.20.0',
        'lxml-asserts',
        'tornado-httpclient-mock',
    ],
    dependency_links=[
        'https://github.com/tornadoweb/tornado/archive/master.zip',
        'https://github.com/hhru/balancing-http-client/archive/1.0.1.zip#egg=balancing-http-client-1.0.1',
    ],
    extras_require={
        'sentry': ['raven'],
        'kafka': ['aiokafka'],
    },
    zip_safe=False
)
