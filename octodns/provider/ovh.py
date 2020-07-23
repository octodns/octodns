#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

import base64
import binascii
import logging
from collections import defaultdict
from six import text_type

import ovh
from ovh import ResourceNotFoundError

from octodns.record import Record
from .base import BaseProvider


class OvhProvider(BaseProvider):
    """
    OVH provider using API v6

    ovh:
        class: octodns.provider.ovh.OvhProvider
        # OVH api v6 endpoint
        endpoint: ovh-eu
        # API application key
        application_key: 1234
        # API application secret
        application_secret: 1234
        # API consumer key
        consumer_key: 1234
    """

    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS_ROOT_NS = False
    ZONE_NOT_FOUND_MESSAGE = 'This service does not exist'

    # This variable is also used in populate method to filter which OVH record
    # types are supported by octodns
    SUPPORTS = set(('A', 'AAAA', 'CAA', 'CNAME', 'DKIM', 'MX', 'NAPTR', 'NS',
                    'PTR', 'SPF', 'SRV', 'SSHFP', 'TXT'))

    def __init__(self, id, endpoint, application_key, application_secret,
                 consumer_key, *args, **kwargs):
        self.log = logging.getLogger('OvhProvider[{}]'.format(id))
        self.log.debug('__init__: id=%s, endpoint=%s, application_key=%s, '
                       'application_secret=***, consumer_key=%s', id, endpoint,
                       application_key, consumer_key)
        super(OvhProvider, self).__init__(id, *args, **kwargs)
        self._client = ovh.Client(
            endpoint=endpoint,
            application_key=application_key,
            application_secret=application_secret,
            consumer_key=consumer_key,
        )

    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s, target=%s, lenient=%s', zone.name,
                       target, lenient)
        zone_name = zone.name[:-1]
        try:
            records = self.get_records(zone_name=zone_name)
            exists = True
        except ResourceNotFoundError as e:
            if text_type(e) != self.ZONE_NOT_FOUND_MESSAGE:
                raise
            exists = False
            records = []

        values = defaultdict(lambda: defaultdict(list))
        for record in records:
            values[record['subDomain']][record['fieldType']].append(record)

        before = len(zone.records)
        for name, types in values.items():
            for _type, records in types.items():
                if _type not in self.SUPPORTS:
                    self.log.warning('Not managed record of type %s, skip',
                                     _type)
                    continue
                data_for = getattr(self, '_data_for_{}'.format(_type))
                record = Record.new(zone, name, data_for(_type, records),
                                    source=self, lenient=lenient)
                zone.add_record(record, lenient=lenient)

        self.log.info('populate:   found %s records, exists=%s',
                      len(zone.records) - before, exists)
        return exists

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        zone_name = desired.name[:-1]
        self.log.info('_apply: zone=%s, len(changes)=%d', desired.name,
                      len(changes))
        for change in changes:
            class_name = change.__class__.__name__
            getattr(self, '_apply_{}'.format(class_name).lower())(zone_name,
                                                                  change)

        # We need to refresh the zone to really apply the changes
        self._client.post('/domain/zone/{}/refresh'.format(zone_name))

    def _apply_create(self, zone_name, change):
        new = change.new
        params_for = getattr(self, '_params_for_{}'.format(new._type))
        for params in params_for(new):
            self.create_record(zone_name, params)

    def _apply_update(self, zone_name, change):
        self._apply_delete(zone_name, change)
        self._apply_create(zone_name, change)

    def _apply_delete(self, zone_name, change):
        existing = change.existing
        record_type = existing._type
        if record_type == "TXT":
            if self._is_valid_dkim(existing.values[0]):
                record_type = 'DKIM'
        self.delete_records(zone_name, record_type, existing.name)

    @staticmethod
    def _data_for_multiple(_type, records):
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': [record['target'] for record in records]
        }

    @staticmethod
    def _data_for_single(_type, records):
        record = records[0]
        return {
            'ttl': record['ttl'],
            'type': _type,
            'value': record['target']
        }

    @staticmethod
    def _data_for_CAA(_type, records):
        values = []
        for record in records:
            flags, tag, value = record['target'].split(' ', 2)
            values.append({
                'flags': flags,
                'tag': tag,
                'value': value[1:-1]
            })
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': values
        }

    @staticmethod
    def _data_for_MX(_type, records):
        values = []
        for record in records:
            preference, exchange = record['target'].split(' ', 1)
            values.append({
                'preference': preference,
                'exchange': exchange,
            })
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': values,
        }

    @staticmethod
    def _data_for_NAPTR(_type, records):
        values = []
        for record in records:
            order, preference, flags, service, regexp, replacement = record[
                'target'].split(' ', 5)
            values.append({
                'flags': flags[1:-1],
                'order': order,
                'preference': preference,
                'regexp': regexp[1:-1],
                'replacement': replacement,
                'service': service[1:-1],
            })
        return {
            'type': _type,
            'ttl': records[0]['ttl'],
            'values': values
        }

    @staticmethod
    def _data_for_SRV(_type, records):
        values = []
        for record in records:
            priority, weight, port, target = record['target'].split(' ', 3)
            values.append({
                'port': port,
                'priority': priority,
                'target': '{}.'.format(target),
                'weight': weight
            })
        return {
            'type': _type,
            'ttl': records[0]['ttl'],
            'values': values
        }

    @staticmethod
    def _data_for_SSHFP(_type, records):
        values = []
        for record in records:
            algorithm, fingerprint_type, fingerprint = record['target'].split(
                ' ', 2)
            values.append({
                'algorithm': algorithm,
                'fingerprint': fingerprint,
                'fingerprint_type': fingerprint_type
            })
        return {
            'type': _type,
            'ttl': records[0]['ttl'],
            'values': values
        }

    @staticmethod
    def _data_for_DKIM(_type, records):
        return {
            'ttl': records[0]['ttl'],
            'type': "TXT",
            'values': [record['target'].replace(';', '\\;')
                       for record in records]
        }

    _data_for_A = _data_for_multiple
    _data_for_AAAA = _data_for_multiple
    _data_for_NS = _data_for_multiple
    _data_for_TXT = _data_for_multiple
    _data_for_SPF = _data_for_multiple
    _data_for_PTR = _data_for_single
    _data_for_CNAME = _data_for_single

    @staticmethod
    def _params_for_multiple(record):
        for value in record.values:
            yield {
                'target': value,
                'subDomain': record.name,
                'ttl': record.ttl,
                'fieldType': record._type,
            }

    @staticmethod
    def _params_for_single(record):
        yield {
            'target': record.value,
            'subDomain': record.name,
            'ttl': record.ttl,
            'fieldType': record._type
        }

    @staticmethod
    def _params_for_CAA(record):
        for value in record.values:
            yield {
                'target': '{} {} "{}"'.format(value.flags, value.tag,
                                              value.value),
                'subDomain': record.name,
                'ttl': record.ttl,
                'fieldType': record._type
            }

    @staticmethod
    def _params_for_MX(record):
        for value in record.values:
            yield {
                'target': '%d %s' % (value.preference, value.exchange),
                'subDomain': record.name,
                'ttl': record.ttl,
                'fieldType': record._type
            }

    @staticmethod
    def _params_for_NAPTR(record):
        for value in record.values:
            content = '{} {} "{}" "{}" "{}" {}' \
                .format(value.order, value.preference, value.flags,
                        value.service, value.regexp, value.replacement)
            yield {
                'target': content,
                'subDomain': record.name,
                'ttl': record.ttl,
                'fieldType': record._type
            }

    @staticmethod
    def _params_for_SRV(record):
        for value in record.values:
            yield {
                'target': '{} {} {} {}'.format(value.priority,
                                               value.weight,
                                               value.port,
                                               value.target),
                'subDomain': record.name,
                'ttl': record.ttl,
                'fieldType': record._type
            }

    @staticmethod
    def _params_for_SSHFP(record):
        for value in record.values:
            yield {
                'target': '{} {} {}'.format(value.algorithm,
                                            value.fingerprint_type,
                                            value.fingerprint),
                'subDomain': record.name,
                'ttl': record.ttl,
                'fieldType': record._type
            }

    def _params_for_TXT(self, record):
        for value in record.values:
            field_type = 'TXT'
            if self._is_valid_dkim(value):
                field_type = 'DKIM'
                value = value.replace("\\;", ";")
            yield {
                'target': value,
                'subDomain': record.name,
                'ttl': record.ttl,
                'fieldType': field_type
            }

    _params_for_A = _params_for_multiple
    _params_for_AAAA = _params_for_multiple
    _params_for_NS = _params_for_multiple
    _params_for_SPF = _params_for_multiple

    _params_for_CNAME = _params_for_single
    _params_for_PTR = _params_for_single

    def _is_valid_dkim(self, value):
        """Check if value is a valid DKIM"""
        validator_dict = {'h': lambda val: val in ['sha1', 'sha256'],
                          's': lambda val: val in ['*', 'email'],
                          't': lambda val: val in ['y', 's'],
                          'v': lambda val: val == 'DKIM1',
                          'k': lambda val: val == 'rsa',
                          'n': lambda _: True,
                          'g': lambda _: True}

        splitted = [v for v in value.split('\\;') if v]
        found_key = False
        for splitted_value in splitted:
            sub_split = [x.strip() for x in splitted_value.split("=", 1)]
            if len(sub_split) < 2:
                return False
            key, value = sub_split[0], sub_split[1]
            if key == "p":
                is_valid_key = self._is_valid_dkim_key(value)
                if not is_valid_key:
                    return False
                found_key = True
            else:
                is_valid_key = validator_dict.get(key, lambda _: False)(value)
                if not is_valid_key:
                    return False
        return found_key

    @staticmethod
    def _is_valid_dkim_key(key):
        try:
            base64.decodestring(bytearray(key, 'utf-8'))
        except binascii.Error:
            return False
        return True

    def get_records(self, zone_name):
        """
        List all records of a DNS zone
        :param zone_name: Name of zone
        :return: list of id's records
        """
        records = self._client.get('/domain/zone/{}/record'.format(zone_name))
        return [self.get_record(zone_name, record_id) for record_id in records]

    def get_record(self, zone_name, record_id):
        """
        Get record with given id
        :param zone_name: Name of the zone
        :param record_id: Id of the record
        :return: Value of the record
        """
        return self._client.get(
            '/domain/zone/{}/record/{}'.format(zone_name, record_id))

    def delete_records(self, zone_name, record_type, subdomain):
        """
        Delete record from have fieldType=type and subDomain=subdomain
        :param zone_name: Name of the zone
        :param record_type: fieldType
        :param subdomain: subDomain
        """
        records = self._client.get('/domain/zone/{}/record'.format(zone_name),
                                   fieldType=record_type, subDomain=subdomain)
        for record in records:
            self.delete_record(zone_name, record)

    def delete_record(self, zone_name, record_id):
        """
        Delete record with a given id
        :param zone_name: Name of the zone
        :param record_id: Id of the record
        """
        self.log.debug('Delete record: zone: %s, id %s', zone_name,
                       record_id)
        self._client.delete(
            '/domain/zone/{}/record/{}'.format(zone_name, record_id))

    def create_record(self, zone_name, params):
        """
        Create a record
        :param zone_name: Name of the zone
        :param params: {'fieldType': 'A', 'ttl': 60, 'subDomain': 'www',
        'target': '1.2.3.4'
        """
        self.log.debug('Create record: zone: %s, id %s', zone_name,
                       params)
        return self._client.post('/domain/zone/{}/record'.format(zone_name),
                                 **params)
