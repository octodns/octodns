#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

import dns.name
import dns.query
import dns.zone
import dns.rdatatype

from dns.exception import DNSException

from collections import defaultdict
from os import listdir
from os.path import join
import logging

from ..record import Record
from .base import BaseSource


class AxfrBaseSource(BaseSource):

    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS_WEIGHTED = False
    SUPPORTS = set(('A', 'AAAA', 'CAA', 'CNAME', 'LOC', 'MX', 'NS', 'PTR',
                    'SPF', 'SRV', 'TXT'))

    def __init__(self, id):
        super(AxfrBaseSource, self).__init__(id)

    def _data_for_multiple(self, _type, records):
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': [r['value'] for r in records]
        }

    _data_for_A = _data_for_multiple
    _data_for_AAAA = _data_for_multiple
    _data_for_NS = _data_for_multiple

    def _data_for_CAA(self, _type, records):
        values = []
        for record in records:
            flags, tag, value = record['value'].split(' ', 2)
            values.append({
                'flags': flags,
                'tag': tag,
                'value': value.replace('"', '')
            })
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': values
        }

    def _data_for_LOC(self, _type, records):
        values = []
        for record in records:
            lat_degrees, lat_minutes, lat_seconds, lat_direction, \
                long_degrees, long_minutes, long_seconds, long_direction, \
                altitude, size, precision_horz, precision_vert = \
                record['value'].replace('m', '').split(' ', 11)
            values.append({
                'lat_degrees': lat_degrees,
                'lat_minutes': lat_minutes,
                'lat_seconds': lat_seconds,
                'lat_direction': lat_direction,
                'long_degrees': long_degrees,
                'long_minutes': long_minutes,
                'long_seconds': long_seconds,
                'long_direction': long_direction,
                'altitude': altitude,
                'size': size,
                'precision_horz': precision_horz,
                'precision_vert': precision_vert,
            })
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': values
        }

    def _data_for_MX(self, _type, records):
        values = []
        for record in records:
            preference, exchange = record['value'].split(' ', 1)
            values.append({
                'preference': preference,
                'exchange': exchange,
            })
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': values
        }

    def _data_for_TXT(self, _type, records):
        values = [value['value'].replace(';', '\\;') for value in records]
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': values
        }

    _data_for_SPF = _data_for_TXT

    def _data_for_single(self, _type, records):
        record = records[0]
        return {
            'ttl': record['ttl'],
            'type': _type,
            'value': record['value']
        }

    _data_for_CNAME = _data_for_single
    _data_for_PTR = _data_for_single

    def _data_for_SRV(self, _type, records):
        values = []
        for record in records:
            priority, weight, port, target = record['value'].split(' ', 3)
            values.append({
                'priority': priority,
                'weight': weight,
                'port': port,
                'target': target,
            })
        return {
            'type': _type,
            'ttl': records[0]['ttl'],
            'values': values
        }

    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s, target=%s, lenient=%s', zone.name,
                       target, lenient)

        values = defaultdict(lambda: defaultdict(list))
        for record in self.zone_records(zone):
            _type = record['type']
            if _type not in self.SUPPORTS:
                continue
            name = zone.hostname_from_fqdn(record['name'])
            values[name][record['type']].append(record)

        before = len(zone.records)
        for name, types in values.items():
            for _type, records in types.items():
                data_for = getattr(self, f'_data_for_{_type}')
                record = Record.new(zone, name, data_for(_type, records),
                                    source=self, lenient=lenient)
                zone.add_record(record, lenient=lenient)

        self.log.info('populate:   found %s records',
                      len(zone.records) - before)


class AxfrSourceException(Exception):
    pass


class AxfrSourceZoneTransferFailed(AxfrSourceException):

    def __init__(self):
        super(AxfrSourceZoneTransferFailed, self).__init__(
            'Unable to Perform Zone Transfer')


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
        super(AxfrSource, self).__init__(id)
        self.master = master

    def zone_records(self, zone):
        try:
            z = dns.zone.from_xfr(dns.query.xfr(self.master, zone.name,
                                                relativize=False),
                                  relativize=False)
        except DNSException:
            raise AxfrSourceZoneTransferFailed()

        records = []

        for (name, ttl, rdata) in z.iterate_rdatas():
            rdtype = dns.rdatatype.to_text(rdata.rdtype)
            records.append({
                "name": name.to_text(),
                "ttl": ttl,
                "type": rdtype,
                "value": rdata.to_text()
            })

        return records


class ZoneFileSourceException(Exception):
    pass


class ZoneFileSourceNotFound(ZoneFileSourceException):

    def __init__(self):
        super(ZoneFileSourceNotFound, self).__init__(
            'Zone file not found')


class ZoneFileSourceLoadFailure(ZoneFileSourceException):

    def __init__(self, error):
        super(ZoneFileSourceLoadFailure, self).__init__(str(error))


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
        self.log.debug('__init__: id=%s, directory=%s, file_extension=%s, '
                       'check_origin=%s', id,
                       directory, file_extension, check_origin)
        super(ZoneFileSource, self).__init__(id)
        self.directory = directory
        self.file_extension = file_extension
        self.check_origin = check_origin

        self._zone_records = {}

    def _load_zone_file(self, zone_name):
        zone_filename = f'{zone_name[:-1]}{self.file_extension}'
        zonefiles = listdir(self.directory)
        if zone_filename in zonefiles:
            try:
                z = dns.zone.from_file(join(self.directory, zone_filename),
                                       zone_name, relativize=False,
                                       check_origin=self.check_origin)
            except DNSException as error:
                raise ZoneFileSourceLoadFailure(error)
        else:
            raise ZoneFileSourceNotFound()

        return z

    def zone_records(self, zone):
        if zone.name not in self._zone_records:
            try:
                z = self._load_zone_file(zone.name)
                records = []
                for (name, ttl, rdata) in z.iterate_rdatas():
                    rdtype = dns.rdatatype.to_text(rdata.rdtype)
                    records.append({
                        "name": name.to_text(),
                        "ttl": ttl,
                        "type": rdtype,
                        "value": rdata.to_text()
                    })

                self._zone_records[zone.name] = records
            except ZoneFileSourceNotFound:
                return []

        return self._zone_records[zone.name]
