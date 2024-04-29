#
#
#

from collections import defaultdict
from ipaddress import ip_address
from logging import getLogger

from ..record import Record
from .base import BaseProcessor


class AutoArpa(BaseProcessor):
    def __init__(
        self,
        name,
        ttl=3600,
        populate_should_replace=False,
        max_auto_arpa=999,
        inherit_ttl=False,
    ):
        super().__init__(name)
        self.log = getLogger(f'AutoArpa[{name}]')
        self.log.info(
            '__init__: ttl=%d, populate_should_replace=%s, max_auto_arpa=%d, inherit_ttl=%s',
            ttl,
            populate_should_replace,
            max_auto_arpa,
            inherit_ttl,
        )
        self.ttl = ttl
        self.populate_should_replace = populate_should_replace
        self.max_auto_arpa = max_auto_arpa
        self.inherit_ttl = inherit_ttl
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
                    auto_arpa_priority = record.octodns.get(
                        'auto_arpa_priority', 999
                    )
                    if self.inherit_ttl:
                        record_ttl = record.ttl
                    else:
                        record_ttl = self.ttl
                    self._records[f'{ptr}.'].append(
                        (auto_arpa_priority, record_ttl, record.fqdn)
                    )

        return desired

    def _order_and_unique_fqdns(self, fqdns, max_auto_arpa):
        seen = set()
        # order the fqdns making a copy so we can reset the list below
        ordered = sorted(fqdns)
        fqdns = []
        for _, record_ttl, fqdn in ordered:
            if fqdn in seen:
                continue
            fqdns.append((record_ttl, fqdn))
            seen.add(fqdn)
            if len(seen) >= max_auto_arpa:
                break
        return fqdns

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
                # Note: this takes a list of (priority, ttl, fqdn) tuples and returns the ordered and uniqified list of fqdns.
                fqdns = self._order_and_unique_fqdns(fqdns, self.max_auto_arpa)
                record = Record.new(
                    zone,
                    name,
                    {
                        'ttl': fqdns[0][0],
                        'type': 'PTR',
                        'values': [fqdn[1] for fqdn in fqdns],
                    },
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
