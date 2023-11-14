#!/usr/bin/env python

from io import StringIO
from os.path import dirname, join

import octodns

try:
    from setuptools import find_packages, setup
except ImportError:
    from distutils.core import find_packages, setup

cmds = ('compare', 'dump', 'report', 'sync', 'validate', 'versions')
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


tests_require = ('pytest>=6.2.5', 'pytest-cov>=3.0.0', 'pytest-network>=0.0.1')

setup(
    author='Ross McFarland',
    author_email='rwmcfa1@gmail.com',
    description=octodns.__doc__,
    entry_points={'console_scripts': console_scripts},
    extras_require={
        'dev': tests_require
        + (
            # we need to manually/explicitely bump major versions as they're
            # likely to result in formatting changes that should happen in their
            # own PR. This will basically happen yearly
            # https://black.readthedocs.io/en/stable/the_black_code_style/index.html#stability-policy
            'black>=23.1.0,<24.0.0',
            'build>=0.7.0',
            'isort>=5.11.5',
            'pycountry>=19.8.18',
            'pycountry-convert>=0.7.2',
            'pyflakes>=2.2.0',
            'readme_renderer[md]>=26.0',
            'twine>=3.4.2',
        )
    },
    install_requires=(
        'PyYaml>=4.2b1',
        'dnspython>=2.2.1',
        'fqdn>=1.5.0',
        'idna>=3.3',
        'natsort>=5.5.0',
        'python-dateutil>=2.8.1',
    ),
    license='MIT',
    long_description=long_description(),
    long_description_content_type='text/markdown',
    name='octodns',
    packages=find_packages(),
    python_requires='>=3.8',
    tests_require=tests_require,
    url='https://github.com/octodns/octodns',
    version=octodns.__version__,
)
