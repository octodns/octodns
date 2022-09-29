#
#
#

import dns.name
import dns.query
import dns.zone
import dns.rdatatype

from dns.exception import DNSException

from os import listdir
from os.path import join
import logging

from ..record import Record, Rr
from .base import BaseSource


class AxfrBaseSource(BaseSource):

    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS = set(
        (
            'A',
            'AAAA',
            'CAA',
            'CNAME',
            'LOC',
            'MX',
            'NS',
            'PTR',
            'SPF',
            'SRV',
            'SSHFP',
            'TXT',
        )
    )

    def __init__(self, id):
        super().__init__(id)

    def populate(self, zone, target=False, lenient=False):
        self.log.debug(
            'populate: name=%s, target=%s, lenient=%s',
            zone.name,
            target,
            lenient,
        )

        before = len(zone.records)
        rrs = self.zone_records(zone)
        for record in Record.from_rrs(zone, rrs, lenient=lenient):
            zone.add_record(record, lenient=lenient)

        self.log.info(
            'populate:   found %s records', len(zone.records) - before
        )


class AxfrSourceException(Exception):
    pass


class AxfrSourceZoneTransferFailed(AxfrSourceException):
    def __init__(self):
        super().__init__('Unable to Perform Zone Transfer')


class AxfrSource(AxfrBaseSource):
    '''
    Axfr zonefile importer to import data

    axfr:
        class: octodns.source.axfr.AxfrSource
        # The address of nameserver to perform zone transfer against
        master: ns1.example.com
    '''

    def __init__(self, id, master):
        self.log = logging.getLogger(f'AxfrSource[{id}]')
        self.log.debug('__init__: id=%s, master=%s', id, master)
        super().__init__(id)
        self.master = master

    def zone_records(self, zone):
        try:
            z = dns.zone.from_xfr(
                dns.query.xfr(self.master, zone.name, relativize=False),
                relativize=False,
            )
        except DNSException:
            raise AxfrSourceZoneTransferFailed()

        records = []

        for (name, ttl, rdata) in z.iterate_rdatas():
            rdtype = dns.rdatatype.to_text(rdata.rdtype)
            if rdtype in self.SUPPORTS:
                records.append(Rr(name.to_text(), rdtype, ttl, rdata.to_text()))

        return records


class ZoneFileSourceException(Exception):
    pass


class ZoneFileSourceNotFound(ZoneFileSourceException):
    def __init__(self):
        super().__init__('Zone file not found')


class ZoneFileSourceLoadFailure(ZoneFileSourceException):
    def __init__(self, error):
        super().__init__(str(error))


class ZoneFileSource(AxfrBaseSource):
    '''
    Bind compatible zone file source

    zonefile:
        class: octodns.source.axfr.ZoneFileSource
        # The directory holding the zone files
        # Filenames should match zone name (eg. example.com.)
        # with optional extension specified with file_extension
        directory: ./zonefiles
        # File extension on zone files
        # Appended to zone name to locate file
        # (optional, default None)
        file_extension: zone
        # Should sanity checks of the origin node be done
        # (optional, default true)
        check_origin: false
    '''

    def __init__(self, id, directory, file_extension='.', check_origin=True):
        self.log = logging.getLogger(f'ZoneFileSource[{id}]')
        self.log.debug(
            '__init__: id=%s, directory=%s, file_extension=%s, '
            'check_origin=%s',
            id,
            directory,
            file_extension,
            check_origin,
        )
        super().__init__(id)
        self.directory = directory
        self.file_extension = file_extension
        self.check_origin = check_origin

        self._zone_records = {}

    def _load_zone_file(self, zone_name):
        zone_filename = f'{zone_name[:-1]}{self.file_extension}'
        zonefiles = listdir(self.directory)
        if zone_filename in zonefiles:
            try:
                z = dns.zone.from_file(
                    join(self.directory, zone_filename),
                    zone_name,
                    relativize=False,
                    check_origin=self.check_origin,
                )
            except DNSException as error:
                raise ZoneFileSourceLoadFailure(error)
        else:
            raise ZoneFileSourceNotFound()

        return z

    def zone_records(self, zone):
        if zone.name not in self._zone_records:
            try:
                z = self._load_zone_file(zone.name)
            except ZoneFileSourceNotFound:
                return []

            records = []
            for (name, ttl, rdata) in z.iterate_rdatas():
                rdtype = dns.rdatatype.to_text(rdata.rdtype)
                if rdtype in self.SUPPORTS:
                    records.append(
                        Rr(name.to_text(), rdtype, ttl, rdata.to_text())
                    )

            self._zone_records[zone.name] = records

        return self._zone_records[zone.name]
