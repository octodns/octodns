#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

import logging
from collections import defaultdict

import ovh

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

    SUPPORTS = set(('A', 'AAAA', 'CNAME', 'MX', 'NAPTR', 'NS', 'PTR', 'SPF',
                    'SRV', 'SSHFP', 'TXT'))

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
        records = self.get_records(zone_name=zone_name)

        values = defaultdict(lambda: defaultdict(list))
        for record in records:
            values[record['subDomain']][record['fieldType']].append(record)

        before = len(zone.records)
        for name, types in values.items():
            for _type, records in types.items():
                data_for = getattr(self, '_data_for_{}'.format(_type))
                record = Record.new(zone, name, data_for(_type, records),
                                    source=self, lenient=lenient)
                zone.add_record(record)

        self.log.info('populate:   found %s records',
                      len(zone.records) - before)

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
        self.delete_records(zone_name, existing._type, existing.name)

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
                'subDomain': '{} {} {} {}'.format(value.priority,
                                                  value.weight, value.port,
                                                  value.target),
                'target': record.name,
                'ttl': record.ttl,
                'fieldType': record._type
            }

    @staticmethod
    def _params_for_SSHFP(record):
        for value in record.values:
            yield {
                'subDomain': '{} {} {}'.format(value.algorithm,
                                               value.fingerprint_type,
                                               value.fingerprint),
                'target': record.name,
                'ttl': record.ttl,
                'fieldType': record._type
            }

    _params_for_A = _params_for_multiple
    _params_for_AAAA = _params_for_multiple
    _params_for_NS = _params_for_multiple
    _params_for_SPF = _params_for_multiple
    _params_for_TXT = _params_for_multiple

    _params_for_CNAME = _params_for_single
    _params_for_PTR = _params_for_single

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
