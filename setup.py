#!/usr/bin/env python

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
from os.path import dirname, join
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
    'validate'
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
    buf = buf.getvalue()
    with open('/tmp/mod', 'w') as fh:
        fh.write(buf)
    return buf


setup(
    author='Ross McFarland',
    author_email='rwmcfa1@gmail.com',
    description=octodns.__doc__,
    entry_points={
        'console_scripts': console_scripts,
    },
    install_requires=[
        'PyYaml>=4.2b1',
        'dnspython>=1.15.0',
        'futures>=3.2.0; python_version<"3.2"',
        'ipaddress>=1.0.22',
        'natsort>=5.5.0',
        'pycountry>=19.8.18',
        'pycountry-convert>=0.7.2',
        'python-dateutil>=2.8.1',
        'requests>=2.20.0'
    ],
    license='MIT',
    long_description=long_description(),
    long_description_content_type='text/markdown',
    name='octodns',
    packages=find_packages(),
    url='https://github.com/github/octodns',
    version=octodns.__VERSION__,
)
