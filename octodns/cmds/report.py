#!/usr/bin/env python
'''
Octo-DNS Reporter
'''

import asyncio
import csv
import io
import ipaddress
import json
import sys
from collections import defaultdict
from logging import getLogger

import dns.asyncresolver
import dns.resolver

from octodns.cmds.args import ArgumentParser
from octodns.manager import Manager


async def async_resolve(record, resolver, timeout, limit):
    async with limit:
        r = dns.asyncresolver.Resolver(configure=False)
        r.lifetime = timeout
        r.nameservers = [resolver]

        try:
            query = await r.resolve(qname=record.fqdn, rdtype=record._type)
            answer = [str(a) for a in query]
        except (dns.resolver.NoAnswer, dns.resolver.NoNameservers):
            answer = ['*no answer*']
        except dns.resolver.NXDOMAIN:
            answer = ['*does not exist*']
        except dns.resolver.YXDOMAIN:
            answer = ['*should not exist*']
        except dns.resolver.LifetimeTimeout:
            answer = ['*timeout*']

    return [record, resolver, sorted(answer)]


def main():
    parser = ArgumentParser(description=__doc__.split('\n')[1])

    parser.add_argument(
        '--config-file',
        required=True,
        help='The Manager configuration file to use',
    )
    parser.add_argument('--zone', required=True, help='Zone to dump')
    parser.add_argument(
        '--source',
        required=True,
        default=[],
        action='append',
        help='Source(s) to pull data from',
    )
    parser.add_argument(
        '--concurrency',
        type=int,
        default=10,
        help='Maximum number of concurrent DNS queries',
    )
    parser.add_argument(
        '--timeout',
        type=float,
        default=1,
        help='Number seconds to wait for an answer',
    )
    parser.add_argument(
        '--output-format',
        choices=['csv', 'json'],
        default='csv',
        help='Output format',
    )
    parser.add_argument(
        '--lenient',
        action='store_true',
        default=False,
        help='Ignore record validations and do a best effort dump',
    )
    parser.add_argument('server', nargs='+', help='DNS resolver to query')

    args = parser.parse_args()
    concurrency = args.concurrency
    timeout = args.timeout
    output_format = args.output_format

    manager = Manager(args.config_file)

    log = getLogger('report')
    log.info(f'concurrency={concurrency} timeout={timeout}')

    try:
        sources = [manager.providers[source] for source in args.source]
    except KeyError as e:
        raise Exception(f'Unknown source: {e.args[0]}')

    zone = manager.get_zone(args.zone)
    for source in sources:
        source.populate(zone, lenient=args.lenient)

    servers = args.server
    resolvers = []
    for server in servers:
        resolver = None
        is_hostname = False

        try:
            ip = ipaddress.ip_address(server)
            # "2001:4860:4860:0:0:0:0:8888" => "2001:4860:4860::8888"
            resolver = ip.compressed

        # The specified server isn't a valid IP address, maybe it's a valid
        # hostname? So we try to resolve it.
        except ValueError:
            # IPv4 first, then IPv6.
            for rrtype in ['A', 'AAAA']:
                try:
                    query = dns.resolver.resolve(server, rrtype)
                    resolver = str(query.rrset[0])
                    is_hostname = True
                    # Exit on first IP address found.
                    break

                # NXDOMAIN, NoAnswer, NoNameservers...
                except:
                    continue

        if resolver and not resolver in resolvers:
            if not is_hostname:
                log.info(f'server={resolver}')
            else:
                log.info(f'server={resolver} ({server})')

            resolvers.append(resolver)

    if not resolvers:
        print(f'Error: No valid resolver specified ({', '.join(servers)})')
        sys.exit(1)

    loop = asyncio.new_event_loop()
    limit = asyncio.Semaphore(concurrency)
    tasks = []
    for record in sorted(zone.records):
        for resolver in resolvers:
            tasks.append(
                loop.create_task(
                    async_resolve(record, resolver, timeout, limit)
                )
            )

    queries = defaultdict(dict)
    done, _ = loop.run_until_complete(asyncio.wait(tasks))
    for task in done:
        _record, _resolver, _answer = task.result()
        queries[_record][_resolver] = _answer

    loop.close()

    output = io.StringIO()
    if output_format == 'csv':
        csvout = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        csvheader = ['Name', 'Type', 'TTL']
        csvheader = [*csvheader, *resolvers]
        csvheader.append('Consistent')
        csvout.writerow(csvheader)

        for record, answers in sorted(queries.items()):
            csvrow = [record.decoded_fqdn, record._type, record.ttl]
            values_check = {}

            for resolver in resolvers:
                answer = f'{' '.join(answers.get(resolver))}'
                values_check[answer.lower()] = True
                csvrow.append(answer)

            csvrow.append(bool(len(values_check) == 1))
            csvout.writerow(csvrow)

    elif output_format == 'json':
        jsonout = defaultdict(lambda: defaultdict(dict))
        for record, answers in sorted(queries.items()):
            values_check = {}

            for resolver in resolvers:
                answer = answers.get(resolver)
                jsonout[record.fqdn][record._type][resolver] = answer
                values_check[f'{' '.join(answer)}'.lower()] = True

            jsonout[record.fqdn][record._type]['consistent'] = bool(
                len(values_check) == 1
            )

        json.dump(jsonout, output)

    print(output.getvalue())
    output.close()


if __name__ == '__main__':
    main()
