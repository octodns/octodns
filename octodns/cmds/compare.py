#!/usr/bin/env python
'''
Octo-DNS Comparator
'''

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from pprint import pprint

from octodns.cmds.args import ArgumentParser
from octodns.manager import Manager


def main():
    parser = ArgumentParser(description=__doc__.split('\n')[1])

    parser.add_argument('--config-file', required=True,
                        help='The Manager configuration file to use')
    parser.add_argument('--a', nargs='+', required=True,
                        help='First source(s) to pull data from')
    parser.add_argument('--b', nargs='+', required=True,
                        help='Second source(s) to pull data from')
    parser.add_argument('--zone', default=None, required=True,
                        help='Zone to compare')

    args = parser.parse_args()

    manager = Manager(args.config_file)
    changes = manager.compare(args.a, args.b, args.zone)
    pprint(changes)


if __name__ == '__main__':
    main()
