from __future__ import annotations

from collections import defaultdict
from ipaddress import ip_address
from logging import Logger, getLogger
from typing import Any, Iterable

from ..record import Record
from ..zone import Zone
from .base import BaseProcessor


class AutoArpa(BaseProcessor):
    def __init__(
        self,
        name: str,
        ttl: int = 3600,
        populate_should_replace: bool = False,
        max_auto_arpa: int = 999,
        inherit_ttl: bool = False,
        wildcard_replacement: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(name, **kwargs)
        self.log: Logger = getLogger(f'AutoArpa[{name}]')
        self.log.info(
            '__init__: ttl=%d, populate_should_replace=%s, max_auto_arpa=%d, inherit_ttl=%s, wildcard_replacement=%s',
            ttl,
            populate_should_replace,
            max_auto_arpa,
            inherit_ttl,
            wildcard_replacement,
        )
        self.ttl = ttl
        self.populate_should_replace = populate_should_replace
        self.max_auto_arpa = max_auto_arpa
        self.inherit_ttl = inherit_ttl
        self.wildcard_replacement = wildcard_replacement
        self._records: dict[str, list[tuple[int, int, str]]] = defaultdict(list)

    def process_source_zone(
        self, desired: Zone, sources: Iterable[Any], lenient: bool = False
    ) -> Zone:
        for record in desired.records:
            if record._type in ('A', 'AAAA') and (  # type: ignore[attr-defined]
                record.name != '*' or self.wildcard_replacement is not None
            ):
                ips = record.values
                if record.geo:  # type: ignore[attr-defined]
                    for geo in record.geo.values():  # type: ignore[attr-defined]
                        ips += geo.values  # type: ignore[attr-defined]
                if record.dynamic:  # type: ignore[attr-defined]
                    for pool in record.dynamic.pools.values():  # type: ignore[attr-defined]
                        for value in pool.data['values']:  # type: ignore[attr-defined]
                            ips.append(value['value'])

                fqdn = record.fqdn
                if self.wildcard_replacement is not None:
                    fqdn = fqdn.replace('*', self.wildcard_replacement)
                for ip in ips:
                    ptr = ip_address(ip).reverse_pointer
                    auto_arpa_priority = record.octodns.get(  # type: ignore[attr-defined]
                        'auto_arpa_priority', 999
                    )
                    if self.inherit_ttl:
                        record_ttl = record.ttl  # type: ignore[attr-defined]
                    else:
                        record_ttl = self.ttl
                    self._records[f'{ptr}.'].append(
                        (auto_arpa_priority, record_ttl, fqdn)
                    )

        return desired

    def _order_and_unique_fqdns(
        self, fqdns: list[tuple[int, int, str]], max_auto_arpa: int
    ) -> list[tuple[int, str]]:
        seen: set[str] = set()
        # order the fqdns making a copy so we can reset the list below
        ordered = sorted(fqdns)
        fqdns_out: list[tuple[int, str]] = []
        for _, record_ttl, fqdn in ordered:
            if fqdn in seen:
                continue
            fqdns_out.append((record_ttl, fqdn))
            seen.add(fqdn)
            if len(seen) >= max_auto_arpa:
                break
        return fqdns_out

    def populate(
        self, zone: Zone, target: bool = False, lenient: bool = False
    ) -> None:
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
                ordered_fqdns = self._order_and_unique_fqdns(
                    fqdns, self.max_auto_arpa
                )
                record = Record.new(
                    zone,
                    name,
                    {
                        'ttl': ordered_fqdns[0][0],
                        'type': 'PTR',
                        'values': [fqdn[1] for fqdn in ordered_fqdns],
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

    def list_zones(self) -> set[str]:
        return set()
