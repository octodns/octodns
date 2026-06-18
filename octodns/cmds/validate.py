#!/usr/bin/env python
'''
Octo-DNS Validator
'''

from logging import WARNING, getLogger
from sys import exit

from octodns.cmds.args import ArgumentParser
from octodns.manager import Manager


class FlaggingHandler:
    level = WARNING

    def __init__(self):
        self.flag = False

    def handle(self, record):
        self.flag = True


def main():
    parser = ArgumentParser(description=__doc__.split('\n')[1])

    parser.add_argument(
        '--config-file',
        required=True,
        help='The Manager configuration file to use',
    )
    parser.add_argument(
        '--all',
        action='store_true',
        default=False,
        help='Validate records in lenient mode, printing warnings so that all validation issues are shown',
    )
    parser.add_argument(
        '--honor-lenient',
        action='store_true',
        default=False,
        help='Suppress warnings for zones and records configured with lenient: true, exiting 0 if no non-lenient issues remain',
    )

    args = parser.parse_args(WARNING)

    flagging = FlaggingHandler()
    getLogger('Record').addHandler(flagging)
    getLogger('Zone').addHandler(flagging)

    manager = Manager(args.config_file)
    manager.validate_configs(
        lenient=args.all, suppress_lenient_warnings=args.honor_lenient
    )

    if flagging.flag:
        exit(1)


if __name__ == '__main__':
    main()
