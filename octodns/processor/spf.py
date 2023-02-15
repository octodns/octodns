#
#
#

from logging import getLogger

import dns.resolver

from octodns.record.base import Record

from .base import BaseProcessor, ProcessorException


class SpfValueException(ProcessorException):
    pass


class SpfDnsLookupException(ProcessorException):
    pass


class SpfDnsLookupProcessor(BaseProcessor):
    log = getLogger('SpfDnsLookupProcessor')

    def __init__(self, name):
        self.log.debug(f"SpfDnsLookupProcessor: {name}")
        super().__init__(name)

    def _lookup(
        self, record: Record, values: list[str], lookups: int = 0
    ) -> int:
        # SPF values must begin with 'v=spf1 '
        spf = [value for value in values if value.startswith('v=spf1 ')]

        if len(spf) == 0:
            return lookups

        if len(spf) > 1:
            raise SpfValueException(
                f"{record.fqdn} has more than one SPF value"
            )

        spf = spf[0]

        terms = spf.removeprefix('v=spf1 ').split(' ')

        for term in terms:
            if lookups > 10:
                raise SpfDnsLookupException(
                    f"{record.fqdn} exceeds the 10 DNS lookup limit in the SPF record"
                )

            # These mechanisms cost one DNS lookup each
            if term.startswith(
                ('a', 'mx', 'exists:', 'redirect', 'include:', 'ptr')
            ):
                lookups += 1

            # The include mechanism can result in further lookups after resolving the DNS record
            if term.startswith('include:'):
                answer = dns.resolver.resolve(
                    term.removeprefix('include:'), 'TXT'
                )
                lookups = self._lookup(
                    record, [value.to_text()[1:-1] for value in answer], lookups
                )

        return lookups

    def process_source_zone(self, zone, *args, **kwargs):
        for record in zone.records:
            if record._type != 'TXT':
                continue

            if record._octodns.get('lenient'):
                continue

            self._lookup(record, record.values)

        return zone
