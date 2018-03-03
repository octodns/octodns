#!/usr/bin/env python
'''
Octo-DNS Reporter
'''

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from concurrent.futures import ThreadPoolExecutor
from dns.exception import Timeout
from dns.resolver import NXDOMAIN, NoAnswer, NoNameservers, Resolver, query
from logging import getLogger
from sys import stdout
import re

from octodns.cmds.args import ArgumentParser
from octodns.manager import Manager
from octodns.zone import Zone


class AsyncResolver(Resolver):

    def __init__(self, num_workers, *args, **kwargs):
        super(AsyncResolver, self).__init__(*args, **kwargs)
        self.executor = ThreadPoolExecutor(max_workers=num_workers)

    def query(self, *args, **kwargs):
        return self.executor.submit(super(AsyncResolver, self).query, *args,
                                    **kwargs)


def main():
    parser = ArgumentParser(description=__doc__.split('\n')[1])

    parser.add_argument('--config-file', required=True,
                        help='The Manager configuration file to use')
    parser.add_argument('--zone', required=True, help='Zone to dump')
    parser.add_argument('--source', required=True, default=[], action='append',
                        help='Source(s) to pull data from')
    parser.add_argument('--num-workers', default=4,
                        help='Number of background workers')
    parser.add_argument('--timeout', default=1,
                        help='Number seconds to wait for an answer')
    parser.add_argument('server', nargs='+', help='Servers to query')

    args = parser.parse_args()

    manager = Manager(args.config_file)

    log = getLogger('report')

    try:
        sources = [manager.providers[source] for source in args.source]
    except KeyError as e:
        raise Exception('Unknown source: {}'.format(e.args[0]))

    zone = Zone(args.zone, manager.configured_sub_zones(args.zone))
    for source in sources:
        source.populate(zone)

    print('name,type,ttl,{},consistent'.format(','.join(args.server)))
    resolvers = []
    ip_addr_re = re.compile(r'^[\d\.]+$')
    for server in args.server:
        resolver = AsyncResolver(configure=False,
                                 num_workers=int(args.num_workers))
        if not ip_addr_re.match(server):
            server = unicode(query(server, 'A')[0])
        log.info('server=%s', server)
        resolver.nameservers = [server]
        resolver.lifetime = int(args.timeout)
        resolvers.append(resolver)

    queries = {}
    for record in sorted(zone.records):
        queries[record] = [r.query(record.fqdn, record._type)
                           for r in resolvers]

    for record, futures in sorted(queries.items(), key=lambda d: d[0]):
        stdout.write(record.fqdn)
        stdout.write(',')
        stdout.write(record._type)
        stdout.write(',')
        stdout.write(unicode(record.ttl))
        compare = {}
        for future in futures:
            stdout.write(',')
            try:
                answers = [unicode(r) for r in future.result()]
            except (NoAnswer, NoNameservers):
                answers = ['*no answer*']
            except NXDOMAIN:
                answers = ['*does not exist*']
            except Timeout:
                answers = ['*timeout*']
            stdout.write(' '.join(answers))
            # sorting to ignore order
            answers = '*:*'.join(sorted(answers)).lower()
            compare[answers] = True
        stdout.write(',True\n' if len(compare) == 1 else ',False\n')


if __name__ == '__main__':
    main()
