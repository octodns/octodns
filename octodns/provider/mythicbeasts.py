#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

import re

from requests import Session
from logging import getLogger

from ..record import Record
from .base import BaseProvider

from collections import defaultdict


def add_trailing_dot(value):
    '''
    Add trailing dots to values
    '''
    assert value, 'Missing value'
    assert value[-1] != '.', 'Value already has trailing dot'
    return value + '.'


def remove_trailing_dot(value):
    '''
    Remove trailing dots from values
    '''
    assert value, 'Missing value'
    assert value[-1] == '.', 'Value already missing trailing dot'
    return value[:-1]


class MythicBeastsUnauthorizedException(Exception):
    def __init__(self, zone, *args):
        self.zone = zone
        self.message = 'Mythic Beasts unauthorized for zone: {}'.format(
            self.zone
        )

        super(MythicBeastsUnauthorizedException, self).__init__(
            self.message, self.zone, *args)


class MythicBeastsRecordException(Exception):
    def __init__(self, zone, command, *args):
        self.zone = zone
        self.command = command
        self.message = 'Mythic Beasts could not action command: {} {}'.format(
            self.zone,
            self.command,
        )

        super(MythicBeastsRecordException, self).__init__(
            self.message, self.zone, self.command, *args)


class MythicBeastsProvider(BaseProvider):
    '''
    Mythic Beasts DNS API Provider

    Config settings:

    ---
    providers:
      config:
      ...
      mythicbeasts:
        class: octodns.provider.mythicbeasts.MythicBeastsProvider
          passwords:
            my.domain.: 'password'

    zones:
      my.domain.:
        targets:
          - mythic
    '''

    RE_MX = re.compile(r'^(?P<preference>[0-9]+)\s+(?P<exchange>\S+)$',
                       re.IGNORECASE)

    RE_SRV = re.compile(r'^(?P<priority>[0-9]+)\s+(?P<weight>[0-9]+)\s+'
                        r'(?P<port>[0-9]+)\s+(?P<target>\S+)$',
                        re.IGNORECASE)

    RE_SSHFP = re.compile(r'^(?P<algorithm>[0-9]+)\s+'
                          r'(?P<fingerprint_type>[0-9]+)\s+'
                          r'(?P<fingerprint>\S+)$',
                          re.IGNORECASE)

    RE_CAA = re.compile(r'^(?P<flags>[0-9]+)\s+'
                        r'(?P<tag>issue|issuewild|iodef)\s+'
                        r'(?P<value>\S+)$',
                        re.IGNORECASE)

    RE_POPLINE = re.compile(r'^(?P<name>\S+)\s+(?P<ttl>\d+)\s+'
                            r'(?P<type>\S+)\s+(?P<value>.*)$',
                            re.IGNORECASE)

    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS_ROOT_NS = False
    SUPPORTS = set(('A', 'AAAA', 'ALIAS', 'CNAME', 'MX', 'NS',
                    'SRV', 'SSHFP', 'CAA', 'TXT'))
    BASE = 'https://dnsapi.mythic-beasts.com/'

    def __init__(self, identifier, passwords, *args, **kwargs):
        self.log = getLogger('MythicBeastsProvider[{}]'.format(identifier))

        assert isinstance(passwords, dict), 'Passwords must be a dictionary'

        self.log.debug(
            '__init__: id=%s, registered zones; %s',
            identifier,
            passwords.keys())
        super(MythicBeastsProvider, self).__init__(identifier, *args, **kwargs)

        self._passwords = passwords
        sess = Session()
        self._sess = sess

    def _request(self, method, path, data=None):
        self.log.debug('_request: method=%s, path=%s data=%s',
                       method, path, data)

        resp = self._sess.request(method, path, data=data)
        self.log.debug(
            '_request:   status=%d data=%s',
            resp.status_code,
            resp.text[:20])

        if resp.status_code == 401:
            raise MythicBeastsUnauthorizedException(data['domain'])

        if resp.status_code == 400:
            raise MythicBeastsRecordException(
                data['domain'],
                data['command']
            )
        resp.raise_for_status()
        return resp

    def _post(self, data=None):
        return self._request('POST', self.BASE, data=data)

    def records(self, zone):
        assert zone in self._passwords, 'Missing password for domain: {}' \
            .format(remove_trailing_dot(zone))

        return self._post({
            'domain': remove_trailing_dot(zone),
            'password': self._passwords[zone],
            'showall': 0,
            'command': 'LIST',
        })

    @staticmethod
    def _data_for_single(_type, data):
        return {
            'type': _type,
            'value': data['raw_values'][0]['value'],
            'ttl': data['raw_values'][0]['ttl']
        }

    @staticmethod
    def _data_for_multiple(_type, data):
        return {
            'type': _type,
            'values':
                [raw_values['value'] for raw_values in data['raw_values']],
            'ttl':
                max([raw_values['ttl'] for raw_values in data['raw_values']]),
        }

    @staticmethod
    def _data_for_TXT(_type, data):
        return {
            'type': _type,
            'values':
                [
                    str(raw_values['value']).replace(';', '\\;')
                    for raw_values in data['raw_values']
                ],
            'ttl':
                max([raw_values['ttl'] for raw_values in data['raw_values']]),
        }

    @staticmethod
    def _data_for_MX(_type, data):
        ttl = max([raw_values['ttl'] for raw_values in data['raw_values']])
        values = []

        for raw_value in \
                [raw_values['value'] for raw_values in data['raw_values']]:
            match = MythicBeastsProvider.RE_MX.match(raw_value)

            assert match is not None, 'Unable to parse MX data'

            exchange = match.group('exchange')

            if not exchange.endswith('.'):
                exchange = '{}.{}'.format(exchange, data['zone'])

            values.append({
                'preference': match.group('preference'),
                'exchange': exchange,
            })

        return {
            'type': _type,
            'values': values,
            'ttl': ttl,
        }

    @staticmethod
    def _data_for_CNAME(_type, data):
        ttl = data['raw_values'][0]['ttl']
        value = data['raw_values'][0]['value']
        if not value.endswith('.'):
            value = '{}.{}'.format(value, data['zone'])

        return MythicBeastsProvider._data_for_single(
            _type,
            {'raw_values': [
                {'value': value, 'ttl': ttl}
            ]})

    @staticmethod
    def _data_for_ANAME(_type, data):
        ttl = data['raw_values'][0]['ttl']
        value = data['raw_values'][0]['value']
        return MythicBeastsProvider._data_for_single(
            'ALIAS',
            {'raw_values': [
                {'value': value, 'ttl': ttl}
            ]})

    @staticmethod
    def _data_for_SRV(_type, data):
        ttl = max([raw_values['ttl'] for raw_values in data['raw_values']])
        values = []

        for raw_value in \
                [raw_values['value'] for raw_values in data['raw_values']]:

            match = MythicBeastsProvider.RE_SRV.match(raw_value)

            assert match is not None, 'Unable to parse SRV data'

            target = match.group('target')
            if not target.endswith('.'):
                target = '{}.{}'.format(target, data['zone'])

            values.append({
                'priority': match.group('priority'),
                'weight': match.group('weight'),
                'port': match.group('port'),
                'target': target,
            })

        return {
            'type': _type,
            'values': values,
            'ttl': ttl,
        }

    @staticmethod
    def _data_for_SSHFP(_type, data):
        ttl = max([raw_values['ttl'] for raw_values in data['raw_values']])
        values = []

        for raw_value in \
                [raw_values['value'] for raw_values in data['raw_values']]:
            match = MythicBeastsProvider.RE_SSHFP.match(raw_value)

            assert match is not None, 'Unable to parse SSHFP data'

            values.append({
                'algorithm': match.group('algorithm'),
                'fingerprint_type': match.group('fingerprint_type'),
                'fingerprint': match.group('fingerprint'),
            })

        return {
            'type': _type,
            'values': values,
            'ttl': ttl,
        }

    @staticmethod
    def _data_for_CAA(_type, data):
        ttl = data['raw_values'][0]['ttl']
        raw_value = data['raw_values'][0]['value']

        match = MythicBeastsProvider.RE_CAA.match(raw_value)

        assert match is not None, 'Unable to parse CAA data'

        value = {
            'flags': match.group('flags'),
            'tag': match.group('tag'),
            'value': match.group('value'),
        }

        return MythicBeastsProvider._data_for_single(
            'CAA',
            {'raw_values': [{'value': value, 'ttl': ttl}]})

    _data_for_NS = _data_for_multiple
    _data_for_A = _data_for_multiple
    _data_for_AAAA = _data_for_multiple

    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s, target=%s, lenient=%s', zone.name,
                       target, lenient)

        resp = self.records(zone.name)

        before = len(zone.records)
        exists = False
        data = defaultdict(lambda: defaultdict(lambda: {
            'raw_values': [],
            'name': None,
            'zone': None,
        }))

        exists = True
        for line in resp.content.splitlines():
            match = MythicBeastsProvider.RE_POPLINE.match(line.decode("utf-8"))

            if match is None:
                self.log.debug('failed to match line: %s', line)
                continue

            if match.group(1) == '@':
                _name = ''
            else:
                _name = match.group('name')

            _type = match.group('type')
            _ttl = int(match.group('ttl'))
            _value = match.group('value').strip()

            if hasattr(self, '_data_for_{}'.format(_type)):
                if _name not in data[_type]:
                    data[_type][_name] = {
                        'raw_values': [{'value': _value, 'ttl': _ttl}],
                        'name': _name,
                        'zone': zone.name,
                    }

                else:
                    data[_type][_name].get('raw_values').append(
                        {'value': _value, 'ttl': _ttl}
                    )
            else:
                self.log.debug('skipping %s as not supported', _type)

        for _type in data:
            for _name in data[_type]:
                data_for = getattr(self, '_data_for_{}'.format(_type))

                record = Record.new(
                    zone,
                    _name,
                    data_for(_type, data[_type][_name]),
                    source=self
                )
                zone.add_record(record, lenient=lenient)

        self.log.debug('populate:   found %s records, exists=%s',
                       len(zone.records) - before, exists)

        return exists

    def _compile_commands(self, action, record):
        commands = []

        hostname = remove_trailing_dot(record.fqdn)
        ttl = record.ttl
        _type = record._type

        if _type == 'ALIAS':
            _type = 'ANAME'

        if hasattr(record, 'values'):
            values = record.values
        else:
            values = [record.value]

        base = '{} {} {} {}'.format(action, hostname, ttl, _type)

        # Unescape TXT records
        if _type == 'TXT':
            values = [value.replace('\\;', ';') for value in values]

        # Handle specific types or default
        if _type == 'SSHFP':
            data = values[0].data
            commands.append('{} {} {} {}'.format(
                base,
                data['algorithm'],
                data['fingerprint_type'],
                data['fingerprint']
            ))

        elif _type == 'SRV':
            for value in values:
                data = value.data
                commands.append('{} {} {} {} {}'.format(
                    base,
                    data['priority'],
                    data['weight'],
                    data['port'],
                    data['target']))

        elif _type == 'MX':
            for value in values:
                data = value.data
                commands.append('{} {} {}'.format(
                    base,
                    data['preference'],
                    data['exchange']))

        else:
            if hasattr(self, '_data_for_{}'.format(_type)):
                for value in values:
                    commands.append('{} {}'.format(base, value))
            else:
                self.log.debug('skipping %s as not supported', _type)

        return commands

    def _apply_Create(self, change):
        zone = change.new.zone
        commands = self._compile_commands('ADD', change.new)

        for command in commands:
            self._post({
                'domain': remove_trailing_dot(zone.name),
                'origin': '.',
                'password': self._passwords[zone.name],
                'command': command,
            })
        return True

    def _apply_Update(self, change):
        self._apply_Delete(change)
        self._apply_Create(change)

    def _apply_Delete(self, change):
        zone = change.existing.zone
        commands = self._compile_commands('DELETE', change.existing)

        for command in commands:
            self._post({
                'domain': remove_trailing_dot(zone.name),
                'origin': '.',
                'password': self._passwords[zone.name],
                'command': command,
            })
        return True

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        self.log.debug('_apply: zone=%s, len(changes)=%d', desired.name,
                       len(changes))

        for change in changes:
            class_name = change.__class__.__name__
            getattr(self, '_apply_{}'.format(class_name))(change)
