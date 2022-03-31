#!/usr/bin/env python

from io import StringIO
from os import environ
from os.path import dirname, join
from subprocess import CalledProcessError, check_output
import octodns

try:
    from setuptools import find_packages, setup
except ImportError:
    from distutils.core import find_packages, setup

cmds = (
    'compare',
    'dump',
    'report',
    'sync',
    'validate',
    'versions',
)
cmds_dir = join(dirname(__file__), 'octodns', 'cmds')
console_scripts = {
    'octodns-{name} = octodns.cmds.{name}:main'.format(name=name)
    for name in cmds
}


def long_description():
    buf = StringIO()
    yaml_block = False
    supported_providers = False
    with open('README.md') as fh:
        for line in fh:
            if line == '```yaml\n':
                yaml_block = True
                continue
            elif yaml_block and line == '---\n':
                # skip the line
                continue
            elif yaml_block and line == '```\n':
                yaml_block = False
                continue
            elif supported_providers:
                if line.startswith('## '):
                    supported_providers = False
                    # write this line out, no continue
                else:
                    # We're ignoring this one
                    continue
            elif line == '## Supported providers\n':
                supported_providers = True
                continue
            buf.write(line)
    return buf.getvalue()


def version():
    # pep440 style public & local version numbers
    if environ.get('OCTODNS_RELEASE', False):
        # public
        return octodns.__VERSION__
    try:
        sha = check_output(['git', 'rev-parse', 'HEAD']).decode('utf-8')[:8]
    except (CalledProcessError, FileNotFoundError):
        sha = 'unknown'
    # local
    return f'{octodns.__VERSION__}+{sha}'


tests_require = (
    'pytest>=6.2.5',
    'pytest-cov>=3.0.0',
    'pytest-network>=0.0.1',
)

setup(
    author='Ross McFarland',
    author_email='rwmcfa1@gmail.com',
    description=octodns.__doc__,
    entry_points={
        'console_scripts': console_scripts,
    },
    extras_require={
        'dev': tests_require + (
            'build>=0.7.0',
            'pycodestyle>=2.6.0',
            'pycountry>=19.8.18',
            'pycountry-convert>=0.7.2',
            'pyflakes>=2.2.0',
            'readme_renderer[md]>=26.0',
            'twine>=3.4.2',
        ),
    },
    install_requires=(
        'PyYaml>=4.2b1',
        'dnspython>=1.15.0',
        'fqdn>=1.5.0',
        'natsort>=5.5.0',
        'python-dateutil>=2.8.1',
    ),
    license='MIT',
    long_description=long_description(),
    long_description_content_type='text/markdown',
    name='octodns',
    packages=find_packages(),
    python_requires='>=3.6',
    tests_require=tests_require,
    url='https://github.com/octodns/octodns',
    version=version(),
)
