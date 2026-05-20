#!/usr/bin/env python
'''
octoDNS Versions
'''

from __future__ import annotations

from octodns.cmds.args import ArgumentParser
from octodns.manager import Manager


def main() -> None:
    parser = ArgumentParser(description=__doc__.split('\n')[1])

    parser.add_argument(
        '--config-file',
        required=True,
        help='The Manager configuration file to use',
    )

    args = parser.parse_args()

    Manager(args.config_file)


if __name__ == '__main__':
    main()
