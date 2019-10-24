#!/usr/bin/env python
'''
Octo-DNS Multiplexer
'''

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from octodns.cmds.args import ArgumentParser
from octodns.manager import Manager


def main():
    parser = ArgumentParser(description=__doc__.split('\n')[1])

    parser.add_argument('--config-file', required=True,
                        help='The Manager configuration file to use')
    parser.add_argument('--doit', action='store_true', default=False,
                        help='Whether to take action or just show what would '
                        'change')
    parser.add_argument('--force', action='store_true', default=False,
                        help='Acknowledge that significant changes are being '
                        'made and do them')

    parser.add_argument('zone', nargs='*', default=[],
                        help='Limit sync to the specified zone(s)')

    # --sources isn't an option here b/c filtering sources out would be super
    # dangerous since you could easily end up with an empty zone and delete
    # everything, or even just part of things when there are multiple sources

    parser.add_argument('--target', default=[], action='append',
                        help='Limit sync to the specified target(s)')

    args = parser.parse_args()

    manager = Manager(args.config_file)
    manager.sync(eligible_zones=args.zone, eligible_targets=args.target,
                 dry_run=not args.doit, force=args.force)


if __name__ == '__main__':
    main()
