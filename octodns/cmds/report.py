#!/usr/bin/env python
'''
Octo-DNS Reporter
'''

from asyncio import Semaphore, new_event_loop, wait
from collections import defaultdict
from csv import QUOTE_NONE, writer
from io import StringIO
from ipaddress import ip_address
from json import dump
from logging import getLogger
from sys import exit

from dns.asyncresolver import Resolver as AsyncResolver
from dns.resolver import (
    NXDOMAIN,
    YXDOMAIN,
    LifetimeTimeout,
    NoAnswer,
    NoNameservers,
    resolve,
)

from octodns.cmds.args import ArgumentParser
from octodns.manager import Manager


async def async_resolve(record, resolver, timeout, limit):
    async with limit:
        r = AsyncResolver(configure=False)
        r.lifetime = timeout
        r.nameservers = [resolver]

        try:
            query = await r.resolve(qname=record.fqdn, rdtype=record._type)
            answer = sorted([str(a) for a in query])
        except (NoAnswer, NoNameservers):
            answer = ['*no answer*']
        except NXDOMAIN:
            answer = ['*does not exist*']
        except YXDOMAIN:
            answer = ['*should not exist*']
        except LifetimeTimeout:
            answer = ['*timeout*']

    return [record, resolver, answer]


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
        default=4,
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
            ip = ip_address(server)
            # "2001:4860:4860:0:0:0:0:8888" => "2001:4860:4860::8888"
            resolver = ip.compressed

        # The specified server isn't a valid IP address, maybe it's a valid
        # hostname? So we try to resolve it.
        except ValueError:
            # IPv4 first, then IPv6.
            for rrtype in ['A', 'AAAA']:
                try:
                    query = resolve(server, rrtype)
                    resolver = str(query.rrset[0])
                    is_hostname = True
                    # Exit on first IP address found.
                    break

                # NXDOMAIN, NoAnswer, NoNameservers...
                except Exception:
                    continue

        if resolver and resolver not in resolvers:
            if not is_hostname:
                log.info(f'server={resolver}')
            else:
                log.info(f'server={resolver} ({server})')

            resolvers.append(resolver)

    if not resolvers:
        print(f'Error: No valid resolver specified ({", ".join(servers)})')
        exit(1)

    loop = new_event_loop()
    limit = Semaphore(concurrency)
    tasks = []
    for record in sorted(zone.records):
        for resolver in resolvers:
            tasks.append(
                loop.create_task(
                    async_resolve(record, resolver, timeout, limit)
                )
            )

    queries = defaultdict(dict)
    done, _ = loop.run_until_complete(wait(tasks))
    for task in done:
        _record, _resolver, _answer = task.result()
        queries[_record][_resolver] = _answer

    loop.close()

    output = StringIO()
    if output_format == 'csv':
        csvout = writer(output, quoting=QUOTE_NONE, quotechar=None)
        csvheader = ['Name', 'Type', 'TTL']
        csvheader = [*csvheader, *resolvers]
        csvheader.append('Consistent')
        csvout.writerow(csvheader)

        for record, answers in sorted(queries.items()):
            csvrow = [record.decoded_fqdn, record._type, record.ttl]
            values_check = {}

            for resolver in resolvers:
                answer = ' '.join(answers.get(resolver, []))
                values_check[answer.lower()] = True
                csvrow.append(answer)

            csvrow.append(bool(len(values_check) == 1))
            csvout.writerow(csvrow)

    elif output_format == 'json':
        jsonout = defaultdict(lambda: defaultdict(dict))
        for record, answers in sorted(queries.items()):
            values_check = {}

            for resolver in resolvers:
                # Stripping the surrounding quotes of TXT records values to
                # avoid them being unnecessarily escaped by JSON module.
                answer = [a.strip('"') for a in answers.get(resolver, [])]
                jsonout[record.decoded_fqdn][record._type][resolver] = answer
                values_check[' '.join(answer).lower()] = True

            jsonout[record.fqdn][record._type]['consistent'] = bool(
                len(values_check) == 1
            )

        dump(jsonout, output)

    print(output.getvalue())
    output.close()


if __name__ == '__main__':
    main()
