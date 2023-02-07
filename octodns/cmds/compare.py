#!/usr/bin/env python
'''
Octo-DNS Comparator
'''

import sys
from pprint import pprint

from octodns.cmds.args import ArgumentParser
from octodns.manager import Manager


def main():
    parser = ArgumentParser(description=__doc__.split('\n')[1])

    parser.add_argument(
        '--config-file',
        required=True,
        help='The Manager configuration file to use',
    )
    parser.add_argument(
        '--a',
        nargs='+',
        required=True,
        help='First source(s) to pull data from',
    )
    parser.add_argument(
        '--b',
        nargs='+',
        required=True,
        help='Second source(s) to pull data from',
    )
    parser.add_argument(
        '--zone', default=None, required=True, help='Zone to compare'
    )
    parser.add_argument(
        '--ignore-prefix',
        default=None,
        required=False,
        help='Record prefix to ignore from list of changes',
    )
    args = parser.parse_args()

    manager = Manager(args.config_file)
    changes = manager.compare(args.a, args.b, args.zone)

    # Filter changes list based on ignore-prefix argument if present
    if args.ignore_prefix:
        pattern = args.ignore_prefix
        changes = [c for c in changes if not c.record.fqdn.startswith(pattern)]

    pprint(changes)

    # Exit with non-zero exit code if changes exist
    if len(changes):
        sys.exit(1)


if __name__ == '__main__':
    main()
