#
#
#

from collections import defaultdict
from ipaddress import ip_address
from logging import getLogger

from ..record import Record
from .base import BaseProcessor


class AutoArpa(BaseProcessor):
    def __init__(self, name, ttl=3600, populate_should_replace=False, max_auto_arpa=999):
        super().__init__(name)
        self.log = getLogger(f'AutoArpa[{name}]')
        self.log.info(
            '__init__: ttl=%d, populate_should_replace=%s, max_auto_arpa=%d',
            ttl,
            populate_should_replace,
            max_auto_arpa
        )
        self.ttl = ttl
        self.populate_should_replace = populate_should_replace
        self.max_auto_arpa = max_auto_arpa
        self._records = defaultdict(list)

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
                    auto_arpa_priority = record.octodns.get('auto_arpa_priority', 999)
                    self._records[f'{ptr}.'].append((auto_arpa_priority, record.fqdn))
                    unique_list = list(set(self._records[f'{ptr}.']))
                    self._records[f'{ptr}.'] = unique_list

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
            if arpa.endswith(f'.{zone_name}'):
                name = arpa[:-n]
                fqdns = sorted(fqdns)
                fqdns = [d[1] for d in fqdns]
                fqdns = fqdns[:self.max_auto_arpa]

                record = Record.new(
                    zone,
                    name,
                    {'ttl': self.ttl, 'type': 'PTR', 'values': fqdns},
                    lenient=lenient,
                )
                zone.add_record(
                    record,
                    replace=self.populate_should_replace,
                    lenient=lenient,
                )

        self.log.info(
            'populate:   found %s records', len(zone.records) - before
        )

    def list_zones(self):
        return set()
