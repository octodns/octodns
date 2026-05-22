#!/usr/bin/env python
'''
Octo-DNS Validator
'''

from __future__ import annotations

from logging import WARNING, Handler, getLogger
from sys import exit

from octodns.cmds.args import ArgumentParser
from octodns.manager import Manager


class FlaggingHandler(Handler):
    level = WARNING

    def __init__(self) -> None:
        super().__init__()
        self.flag: bool = False

    def handle(self, record: object) -> bool:
        self.flag = True
        return True


def main() -> None:
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

    args = parser.parse_args(default_log_level=WARNING)

    flagging = FlaggingHandler()
    getLogger('Record').addHandler(flagging)
    getLogger('Zone').addHandler(flagging)

    manager = Manager(args.config_file)
    manager.validate_configs(lenient=args.all)  # type: ignore[attr-defined]

    if flagging.flag:
        exit(1)


if __name__ == '__main__':
    main()
