#!/usr/bin/env python
'''
Octo-DNS Dumper
'''

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from octodns.cmds.args import ArgumentParser
from octodns.manager import Manager


def main():
    parser = ArgumentParser(description=__doc__.split('\n')[1])

    parser.add_argument('--config-file', required=True,
                        help='The Manager configuration file to use')
    parser.add_argument('--output-dir', required=True,
                        help='The directory into which the results will be '
                        'written (Note: will overwrite existing files)')
    parser.add_argument('--lenient', action='store_true', default=False,
                        help='Ignore record validations and do a best effort '
                        'dump')
    parser.add_argument('zone', help='Zone to dump')
    parser.add_argument('source', nargs='+',
                        help='Source(s) to pull data from')

    args = parser.parse_args()

    manager = Manager(args.config_file)
    manager.dump(args.zone, args.output_dir, args.lenient, *args.source)


if __name__ == '__main__':
    main()
