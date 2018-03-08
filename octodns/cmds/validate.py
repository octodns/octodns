#!/usr/bin/env python
'''
Octo-DNS Validator
'''

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import WARN

from octodns.cmds.args import ArgumentParser
from octodns.manager import Manager


def main():
    parser = ArgumentParser(description=__doc__.split('\n')[1])

    parser.add_argument('--config-file', required=True,
                        help='The Manager configuration file to use')
    parser.add_argument('--sort', action='store_true', default=False,
                      help='Sort the zone before sending to validation')

    args = parser.parse_args(WARN)

    manager = Manager(args.config_file)

    if args.sort:
        manager.sort_configs()

    manager.validate_configs()


if __name__ == '__main__':
    main()
