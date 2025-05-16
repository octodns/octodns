import logging
from ipaddress import ip_address

import ifaddr

from ..record import Record
from .base import BaseSource


class NetworkInterfaceSource(BaseSource):
    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS = {'A', 'AAAA'}

    DEFAULT_TTL = 60

    def __init__(
        self,
        id,
        name,
        ttl=DEFAULT_TTL,
        is_global=True,
        is_link_local=False,
        is_loopback=False,
        is_multicast=False,
        is_private=False,
        is_reserved=False,
    ):
        klass = self.__class__.__name__
        self.log = logging.getLogger(f'{klass}[{id}]')
        self.log.setLevel(logging.DEBUG)
        self.log.debug(
            '__init__: id=%s, name=%s, ttl=%d, is_global=%s, is_link_local=%s, is_loopback=%s, is_multicast=%s, is_private=%s, is_reserved=%s',
            id,
            name,
            ttl,
            is_global,
            is_link_local,
            is_loopback,
            is_multicast,
            is_private,
            is_reserved,
        )
        super().__init__(id)
        self.name = name
        self.ttl = ttl
        self.is_global = is_global
        self.is_link_local = is_link_local
        self.is_loopback = is_loopback
        self.is_multicast = is_multicast
        self.is_private = is_private
        self.is_reserved = is_reserved

    @staticmethod
    def _get_ips():  # pragma: no cover
        # The method can not be covered in tests as it has to always get mocked
        ips = []
        for adapter in ifaddr.get_adapters():
            for ip in adapter.ips:
                ips.append(ip)
        return ips

    def populate(self, zone, target=False, lenient=False):
        self.log.debug(
            'populate: name=%s, target=%s, lenient=%s',
            zone.name,
            target,
            lenient,
        )

        before = len(zone.records)

        for ip in self._get_ips():
            value = ip.ip
            record_type = 'A'
            if isinstance(value, tuple):
                value = value[0]
                record_type = 'AAAA'

            parsed_ip = ip_address(value)
            add = False
            for prop in [
                'is_global',
                'is_link_local',
                'is_loopback',
                'is_multicast',
                'is_private',
                'is_reserved',
            ]:
                if getattr(parsed_ip, prop) and getattr(self, prop):
                    add = True
                    break
            if not add:  # pragma: no cover
                continue

            zone.add_record(
                Record.new(
                    zone,
                    self.name,
                    {'ttl': self.ttl, 'type': record_type, 'values': [value]},
                    source=self,
                    lenient=lenient,
                ),
                lenient=lenient,
            )

        self.log.info(
            'populate: found %s records, exists=False',
            len(zone.records) - before,
        )
