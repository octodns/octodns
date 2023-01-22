#
#
#

from collections import defaultdict
from ipaddress import ip_address
from logging import getLogger

from ..record import Record
from .base import BaseProcessor


class AutoArpa(BaseProcessor):
    def __init__(self, name, ttl=3600):
        super().__init__(name)
        self.log = getLogger(f'AutoArpa[{name}]')
        self.ttl = ttl
        self._records = defaultdict(set)

    def process_source_zone(self, desired, sources):
        for record in desired.records:
            if record._type in ('A', 'AAAA'):
                ips = record.values
                if record.geo:
                    for geo in record.geo.values():
                        ips += geo.values
                if record.dynamic:
                    for pool in record.dynamic.pools.values():
                        for value in pool.data['values']:
                            ips.append(value['value'])

                for ip in ips:
                    ptr = ip_address(ip).reverse_pointer
                    self._records[f'{ptr}.'].add(record.fqdn)

        return desired

    def populate(self, zone, target=False, lenient=False):
        self.log.debug(
            'populate: name=%s, target=%s, lenient=%s',
            zone.name,
            target,
            lenient,
        )

        before = len(zone.records)

        zone_name = zone.name
        n = len(zone_name) + 1
        for arpa, fqdns in self._records.items():
            if arpa.endswith(zone_name):
                name = arpa[:-n]
                fqdns = sorted(fqdns)
                record = Record.new(
                    zone,
                    name,
                    {'ttl': self.ttl, 'type': 'PTR', 'values': fqdns},
                )
                zone.add_record(record)

        self.log.info(
            'populate:   found %s records', len(zone.records) - before
        )
