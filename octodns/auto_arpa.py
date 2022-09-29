#
#
#

from collections import defaultdict
from ipaddress import ip_address
from logging import getLogger

from .processor.base import BaseProcessor
from .record import Record
from .source.base import BaseSource


class AutoArpa(BaseProcessor, BaseSource):
    SUPPORTS = set(('PTR',))
    SUPPORTS_GEO = False

    log = getLogger('AutoArpa')

    def __init__(self, ttl=3600):
        super().__init__('auto-arpa')
        self.ttl = ttl

        self._addrs = defaultdict(list)

    def process_source_zone(self, desired, sources):
        for record in desired.records:
            if record._type in ('A', 'AAAA'):
                for value in record.values:
                    addr = ip_address(value)
                    self._addrs[f'{addr.reverse_pointer}.'].append(record.fqdn)

        return desired

    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: zone=%s', zone.name)
        before = len(zone.records)

        name = zone.name
        for arpa, fqdns in self._addrs.items():
            if arpa.endswith(name):
                record = Record.new(
                    zone,
                    zone.hostname_from_fqdn(arpa),
                    {'ttl': self.ttl, 'type': 'PTR', 'values': fqdns},
                )
                zone.add_record(record)

        self.log.info(
            'populate:   found %s records', len(zone.records) - before
        )
