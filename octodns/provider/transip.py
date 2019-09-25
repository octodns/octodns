#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from suds import WebFault

from collections import defaultdict
from .base import BaseProvider
from logging import getLogger
from ..record import Record
from transip.service.domain import DomainService
from transip.service.objects import DnsEntry


class TransipProvider(BaseProvider):
    '''
    Transip DNS provider

    transip:
        class: octodns.provider.transip.TransipProvider
        # Your Transip account name (required)
        account: yourname
        # The api key (required)
        key: |
            \'''
            -----BEGIN PRIVATE KEY-----
            ...
            -----END PRIVATE KEY-----
            \'''

    '''
    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS = set(
        ('A', 'AAAA', 'CNAME', 'MX', 'SRV', 'SPF', 'TXT', 'SSHFP', 'CAA'))
    # unsupported by OctoDNS: 'TLSA'
    MIN_TTL = 120
    TIMEOUT = 15
    ROOT_RECORD = '@'

    def __init__(self, id, account, key, *args, **kwargs):
        self.log = getLogger('TransipProvider[{}]'.format(id))
        self.log.debug('__init__: id=%s, account=%s, token=***', id,
                       account)
        super(TransipProvider, self).__init__(id, *args, **kwargs)

        self._client = DomainService(account, key)

        self.account = account
        self.key = key

        self._zones = None
        self._zone_records = {}

        self._currentZone = {}

    def populate(self, zone, target=False, lenient=False):

        exists = False
        self._currentZone = zone
        self.log.debug('populate: name=%s, target=%s, lenient=%s', zone.name,
                       target, lenient)

        before = len(zone.records)
        try:
            zoneInfo = self._client.get_info(zone.name[:-1])
        except WebFault as e:
            if e.fault.faultcode == '102' and target is False:
                self.log.warning(
                    'populate: (%s) Zone %s not found in account ',
                    e.fault.faultcode, zone.name)
                exists = False
                return exists
            elif e.fault.faultcode == '102' and target is True:
                self.log.warning('populate: Transip can\'t create new zones')
                raise Exception(
                    ('populate: ({}) Transip used ' +
                     'as target for non-existing zone: {}').format(
                        e.fault.faultcode, zone.name))
            else:
                self.log.error('populate: (%s) %s ', e.fault.faultcode,
                               e.fault.faultstring)
                raise e

        self.log.debug('populate: found %s records for zone %s',
                       len(zoneInfo.dnsEntries), zone.name)
        exists = True
        if zoneInfo.dnsEntries:
            values = defaultdict(lambda: defaultdict(list))
            for record in zoneInfo.dnsEntries:
                name = zone.hostname_from_fqdn(record['name'])
                if name == self.ROOT_RECORD:
                    name = ''

                if record['type'] in self.SUPPORTS:
                    values[name][record['type']].append(record)

            for name, types in values.items():
                for _type, records in types.items():
                    data_for = getattr(self, '_data_for_{}'.format(_type))
                    record = Record.new(zone, name, data_for(_type, records),
                                        source=self, lenient=lenient)
                    zone.add_record(record, lenient=lenient)
        self.log.info('populate:   found %s records, exists = %s',
                      len(zone.records) - before, exists)

        self._currentZone = {}
        return exists

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        self.log.debug('apply: zone=%s, changes=%d', desired.name,
                       len(changes))
        # for change in changes:
        #    class_name = change.__class__.__name__
        #    getattr(self, '_apply_{}'.format(class_name))(change)

        self._currentZone = plan.desired
        try:
            self._client.get_info(plan.desired.name[:-1])
        except WebFault as e:
            self.log.warning('_apply: %s ', e.message)
            raise e

        _dns_entries = []
        for record in plan.desired.records:
            if record._type in self.SUPPORTS:
                entries_for = getattr(self,
                                      '_entries_for_{}'.format(record._type))

                # Root records have '@' as name
                name = record.name
                if name == '':
                    name = self.ROOT_RECORD

                _dns_entries.extend(entries_for(name, record))

        try:
            self._client.set_dns_entries(plan.desired.name[:-1], _dns_entries)
        except WebFault as e:
            self.log.warning(('_apply: Set DNS returned ' +
                              'one or more errors: {}').format(
                e.fault.faultstring))
            raise Exception(200, e.fault.faultstring)

        self._currentZone = {}

    def _entries_for_multiple(self, name, record):
        _entries = []

        for value in record.values:
            _entries.append(DnsEntry(name, record.ttl, record._type, value))

        return _entries

    def _entries_for_single(self, name, record):

        return [DnsEntry(name, record.ttl, record._type, record.value)]

    _entries_for_A = _entries_for_multiple
    _entries_for_AAAA = _entries_for_multiple
    _entries_for_NS = _entries_for_multiple
    _entries_for_SPF = _entries_for_multiple
    _entries_for_CNAME = _entries_for_single

    def _entries_for_MX(self, name, record):
        _entries = []

        for value in record.values:
            content = "{} {}".format(value.preference, value.exchange)
            _entries.append(DnsEntry(name, record.ttl, record._type, content))

        return _entries

    def _entries_for_SRV(self, name, record):
        _entries = []

        for value in record.values:
            content = "{} {} {} {}".format(value.priority, value.weight,
                                           value.port, value.target)
            _entries.append(DnsEntry(name, record.ttl, record._type, content))

        return _entries

    def _entries_for_SSHFP(self, name, record):
        _entries = []

        for value in record.values:
            content = "{} {} {}".format(value.algorithm,
                                        value.fingerprint_type,
                                        value.fingerprint)
            _entries.append(DnsEntry(name, record.ttl, record._type, content))

        return _entries

    def _entries_for_CAA(self, name, record):
        _entries = []

        for value in record.values:
            content = "{} {} {}".format(value.flags, value.tag,
                                        value.value)
            _entries.append(DnsEntry(name, record.ttl, record._type, content))

        return _entries

    def _entries_for_TXT(self, name, record):
        _entries = []

        for value in record.values:
            value = value.replace('\\;', ';')
            _entries.append(DnsEntry(name, record.ttl, record._type, value))

        return _entries

    def _parse_to_fqdn(self, value):

        if (value[-1] != '.'):
            self.log.debug('parseToFQDN: changed %s to %s', value,
                           '{}.{}'.format(value, self._currentZone.name))
            value = '{}.{}'.format(value, self._currentZone.name)

        return value

    def _get_lowest_ttl(self, records):
        _ttl = 100000
        for record in records:
            _ttl = min(_ttl, record['expire'])
        return _ttl

    def _data_for_multiple(self, _type, records):

        _values = []
        for record in records:
            _values.append(record['content'])

        return {
            'ttl': self._get_lowest_ttl(records),
            'type': _type,
            'values': _values
        }

    _data_for_A = _data_for_multiple
    _data_for_AAAA = _data_for_multiple
    _data_for_NS = _data_for_multiple
    _data_for_SPF = _data_for_multiple

    def _data_for_CNAME(self, _type, records):
        return {
            'ttl': records[0]['expire'],
            'type': _type,
            'value': self._parse_to_fqdn(records[0]['content'])
        }

    def _data_for_MX(self, _type, records):
        values = []
        for record in records:
            preference, exchange = record['content'].split(" ", 1)
            values.append({
                'preference': preference,
                'exchange': self._parse_to_fqdn(exchange)
            })
        return {
            'ttl': self._get_lowest_ttl(records),
            'type': _type,
            'values': values
        }

    def _data_for_SRV(self, _type, records):
        values = []
        for record in records:
            priority, weight, port, target = record['content'].split(' ', 3)
            values.append({
                'port': port,
                'priority': priority,
                'target': self._parse_to_fqdn(target),
                'weight': weight
            })

        return {
            'type': _type,
            'ttl': self._get_lowest_ttl(records),
            'values': values
        }

    def _data_for_SSHFP(self, _type, records):
        values = []
        for record in records:
            algorithm, fp_type, fingerprint = record['content'].split(' ', 2)
            values.append({
                'algorithm': algorithm,
                'fingerprint': fingerprint.lower(),
                'fingerprint_type': fp_type
            })

        return {
            'type': _type,
            'ttl': self._get_lowest_ttl(records),
            'values': values
        }

    def _data_for_CAA(self, _type, records):
        values = []
        for record in records:
            flags, tag, value = record['content'].split(' ', 2)
            values.append({
                'flags': flags,
                'tag': tag,
                'value': value
            })

        return {
            'type': _type,
            'ttl': self._get_lowest_ttl(records),
            'values': values
        }

    def _data_for_TXT(self, _type, records):
        values = []
        for record in records:
            values.append(record['content'].replace(';', '\\;'))

        return {
            'type': _type,
            'ttl': self._get_lowest_ttl(records),
            'values': values
        }
