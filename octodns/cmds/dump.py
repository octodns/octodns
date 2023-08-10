#!/usr/bin/env python
'''
Octo-DNS Dumper
'''

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
        '--output-dir',
        required=True,
        help='The directory into which the results will be '
        'written (Note: will overwrite existing files)',
    )
    parser.add_argument(
        '--output-provider',
        required=False,
        help='The configured provider to use when dumping '
        'records. Must support copy() and directory',
    )
    parser.add_argument(
        '--lenient',
        action='store_true',
        default=False,
        help='Ignore record validations and do a best effort dump',
    )
    parser.add_argument(
        '--split',
        action='store_true',
        default=False,
        help='Split the dumped zone into a YAML file per record',
    )
    parser.add_argument(
        'zone',
        help="Zone to dump, '*' (single quoted to avoid expansion) for all configured zones",
    )
    parser.add_argument('source', nargs='+', help='Source(s) to pull data from')

    args = parser.parse_args()

    manager = Manager(args.config_file)
    manager.dump(
        zone=args.zone,
        output_dir=args.output_dir,
        output_provider=args.output_provider,
        lenient=args.lenient,
        split=args.split,
        sources=args.source,
    )


if __name__ == '__main__':
    main()
