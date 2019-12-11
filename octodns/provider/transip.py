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


class TransipException(Exception):
    pass


class TransipConfigException(TransipException):
    pass


class TransipNewZoneException(TransipException):
    pass


class TransipProvider(BaseProvider):
    '''
    Transip DNS provider

    transip:
        class: octodns.provider.transip.TransipProvider
        # Your Transip account name (required)
        account: yourname
        # Path to a private key file (required if key is not used)
        key_file: /path/to/file
        # The api key as string (required if key_file is not used)
        key: |
            \'''
            -----BEGIN PRIVATE KEY-----
            ...
            -----END PRIVATE KEY-----
            \'''
        # if both `key_file` and `key` are presented `key_file` is used

    '''
    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS_ROOT_NS = False
    SUPPORTS = set(
        ('A', 'AAAA', 'CNAME', 'MX', 'SRV', 'SPF', 'TXT', 'SSHFP', 'CAA'))
    # unsupported by OctoDNS: 'TLSA'
    MIN_TTL = 120
    TIMEOUT = 15
    ROOT_RECORD = '@'

    def __init__(self, id, account, key=None, key_file=None,  *args, **kwargs):
        self.log = getLogger('TransipProvider[{}]'.format(id))
        self.log.debug('__init__: id=%s, account=%s, token=***', id,
                       account)
        super(TransipProvider, self).__init__(id, *args, **kwargs)

        if key_file is not None:
            self._client = DomainService(account, private_key_file=key_file)
        elif key is not None:
            self._client = DomainService(account, private_key=key)
        else:
            raise TransipConfigException(
                'Missing `key` of `key_file` parameter in config'
            )

        self.account = account
        self.key = key

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
                # Zone not found in account, and not a target so just
                # leave an empty zone.
                return exists
            elif e.fault.faultcode == '102' and target is True:
                self.log.warning('populate: Transip can\'t create new zones')
                raise TransipNewZoneException(
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

        self._currentZone = plan.desired
        try:
            self._client.get_info(plan.desired.name[:-1])
        except WebFault as e:
            self.log.exception('_apply: get_info failed')
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
            raise TransipException(200, e.fault.faultstring)

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

        # Enforce switch from suds.sax.text.Text to string
        value = str(value)

        # TransIP allows '@' as value to alias the root record.
        # this provider won't set an '@' value, but can be an existing record
        if value == self.ROOT_RECORD:
            value = self._currentZone.name

        if value[-1] != '.':
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
            # Enforce switch from suds.sax.text.Text to string
            _values.append(str(record['content']))

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
        _values = []
        for record in records:
            preference, exchange = record['content'].split(" ", 1)
            _values.append({
                'preference': preference,
                'exchange': self._parse_to_fqdn(exchange)
            })
        return {
            'ttl': self._get_lowest_ttl(records),
            'type': _type,
            'values': _values
        }

    def _data_for_SRV(self, _type, records):
        _values = []
        for record in records:
            priority, weight, port, target = record['content'].split(' ', 3)
            _values.append({
                'port': port,
                'priority': priority,
                'target': self._parse_to_fqdn(target),
                'weight': weight
            })

        return {
            'type': _type,
            'ttl': self._get_lowest_ttl(records),
            'values': _values
        }

    def _data_for_SSHFP(self, _type, records):
        _values = []
        for record in records:
            algorithm, fp_type, fingerprint = record['content'].split(' ', 2)
            _values.append({
                'algorithm': algorithm,
                'fingerprint': fingerprint.lower(),
                'fingerprint_type': fp_type
            })

        return {
            'type': _type,
            'ttl': self._get_lowest_ttl(records),
            'values': _values
        }

    def _data_for_CAA(self, _type, records):
        _values = []
        for record in records:
            flags, tag, value = record['content'].split(' ', 2)
            _values.append({
                'flags': flags,
                'tag': tag,
                'value': value
            })

        return {
            'type': _type,
            'ttl': self._get_lowest_ttl(records),
            'values': _values
        }

    def _data_for_TXT(self, _type, records):
        _values = []
        for record in records:
            _values.append(record['content'].replace(';', '\\;'))

        return {
            'type': _type,
            'ttl': self._get_lowest_ttl(records),
            'values': _values
        }
