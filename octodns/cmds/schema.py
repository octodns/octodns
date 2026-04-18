#!/usr/bin/env python
'''
octoDNS JSON Schema generator for zone YAML files
'''

import json
import sys

from octodns.cmds.args import ArgumentParser
from octodns.schema import build_zone_schema


def main():
    parser = ArgumentParser(description=__doc__.split('\n')[1])

    parser.add_argument(
        '--indent',
        type=int,
        default=2,
        help='Number of spaces to indent the JSON output (default: 2)',
    )
    parser.add_argument(
        '--output',
        default=None,
        help='Write schema to this file instead of stdout',
    )

    args = parser.parse_args()

    schema = build_zone_schema()
    data = json.dumps(schema, indent=args.indent, sort_keys=True)

    if args.output:
        with open(args.output, 'w') as fh:
            fh.write(data)
            fh.write('\n')
    else:
        sys.stdout.write(data)
        sys.stdout.write('\n')


if __name__ == '__main__':
    main()
