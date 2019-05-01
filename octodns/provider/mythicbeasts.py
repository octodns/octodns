#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from requests import HTTPError, Session
from logging import getLogger

from ..record import Create, Record
from .base import BaseProvider

import re

import pprint
import sys

def add_trailing_dot(s):
    assert s
    assert s[-1] != '.'
    return s + '.'


def remove_trailing_dot(s):
    assert s
    assert s[-1] == '.'
    return s[:-1]


class MythicBeastsProvider(BaseProvider):
    '''
    Mythic Beasts DNS API Provider

    mythicbeasts:
      class: octodns.provider.mythicbeasts.MythicBeastsProvider
        zones:
          my-zone: 'password'

    '''

    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS = set(('A', 'AAAA', 'CNAME', 'MX', 'NS',
                    'SRV', 'TXT'))
    #BASE = 'https://dnsapi.mythic-beasts.com/'
    BASE = 'https://cwningen.dev.mythic-beasts.com/customer/primarydnsapi'
    TIMEOUT = 15

    def __init__(self, id, passwords, *args, **kwargs):
        self.log = getLogger('MythicBeastsProvider[{}]'.format(id))
        self.log.debug('__init__: id=%s, registered zones; %s', id, passwords.keys())
        super(MythicBeastsProvider, self).__init__(id, *args, **kwargs)

        self._passwords = passwords
        sess = Session()
        self._sess = sess

    def _request(self, method, path, data=None):
        self.log.debug('_request: method=%s, path=%s', method, path)

        url = self.BASE
        resp = self._sess.request(method, url, data=data, timeout=self.TIMEOUT)
        self.log.debug('_request:   status=%d', resp.status_code)
        resp.raise_for_status()
        return resp

    def _post(self, data=None):
        return self._request('POST', self.BASE, data=data)

    def records(self, zone):
        return self._post({
            'domain': remove_trailing_dot(zone),
            'password': self._passwords[zone],
            'showall': 0,
            'command': 'LIST',
        })

    def _data_for_single(self, _type, data):
        return {
            'type': _type,
            'value': data['raw_values'][0]['value'],
            'ttl': data['raw_values'][0]['ttl']
        }

    def _data_for_multiple(self, _type, data):
        return {
            'type': _type,
            'values': [raw_values['value'] for raw_values in data['raw_values']],
            'ttl': max([raw_values['ttl'] for raw_values in data['raw_values']]),
        }

    def _data_for_MX(self, _type, data):
        ttl = max([raw_values['ttl'] for raw_values in data['raw_values']])
        values = []

        for raw_value in [raw_values['value'] for raw_values in data['raw_values']]:
            match = re.match('^([0-9]+)\s+(\S+)$', raw_value, re.IGNORECASE)

            if match is not None:
                exchange = match.group(2)

                if not exchange.endswith('.'):
                    exchange = '{}.{}'.format(exchange, data['zone'])

                values.append({
                    'preference': match.group(1),
                    'exchange': exchange,
                })

        return {
            'type': _type,
            'values': values,
            'ttl': ttl,
        }

    def _data_for_CNAME(self, _type, data):
        ttl = data['raw_values'][0]['ttl']
        value = data['raw_values'][0]['value']
        if not value.endswith('.'):
            value = '{}.{}'.format(value, data['zone'])

        return self._data_for_single(_type, {'raw_values': [ {'value': value, 'ttl': ttl} ]})

    def _data_for_ANAME(self, _type, data):
        ttl = data['raw_values'][0]['ttl']
        value = data['raw_values'][0]['value']
        return self._data_for_single('ALIAS', {'raw_values': [ {'value': value, 'ttl': ttl} ]})
    

    def _data_for_SRV(self, _type, data):
        ttl = data['raw_values'][0]['ttl']
        raw_value = data['raw_values'][0]['value']

        match = re.match('^([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+(\S+)$', raw_value, re.IGNORECASE)

        if match is not None:
            target = match.group(4)
            if not target.endswith('.'):
                target = '{}.{}'.format(target, data['zone'])

            value = {
                'priority': match.group(1),
                'weight': match.group(2),
                'port': match.group(3),
                'target': target,
            }

            return self._data_for_single('SRV', {'raw_values': [ {'value': value, 'ttl': ttl} ]})

    def _data_for_SSHFP(self, _type, data):
        ttl = data['raw_values'][0]['ttl']
        raw_value = data['raw_values'][0]['value']

        match = re.match('^([0-9]+)\s+([0-9]+)\s+(\S+)$', raw_value, re.IGNORECASE)

        if match is not None:
            value = {
                'algorithm': match.group(1),
                'fingerprint_type': match.group(2),
                'fingerprint': match.group(3),
            }

            return self._data_for_single('SSHFP', {'raw_values': [ {'value': value, 'ttl': ttl} ]})
         

    # TODO fix bug with CAA output from API
    '''
    def _data_for_CAA(self, _type, data):
        ttl = data['raw_values'][0]['ttl']

        match = re.match('^()$', re.IGNORECASE)

        value = {
            'flags':
            'tag':
            'value': 
        }
        value = data['raw_values'][0]['value']
        return self._data_for_single('ALIAS', {'raw_values': [ {'value': value, 'ttl': ttl} ]})
    ''' 


    _data_for_NS = _data_for_multiple
    _data_for_TXT = _data_for_multiple
    _data_for_A = _data_for_multiple
    _data_for_AAAA = _data_for_multiple

        
    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s, target=%s, lenient=%s', zone.name,
                       target, lenient)

        resp = None
        try:
            resp = self.records(zone.name)
        except HTTPError as e:
            if e.response.status_code == 401:
                # Nicer error message for auth problems
                raise Exception('Mythic Beasts authentication problem with {}'.format(zone.name))
            elif e.response.status_code == 422:
                # 422 means mythicbeasts doesn't know anything about the requested
                # domain. We'll just ignore it here and leave the zone
                # untouched.
                raise
            else:
                # just re-throw
                raise

        before = len(zone.records)
        exists = False
        data = dict()

        if resp:
            exists = True
            for line in resp.content.splitlines():
                match = re.match('^(\S+)\s+(\S+)\s+(\S+)\s+(.*)$', line, re.IGNORECASE)

                if match is not None:
                    if match.group(1) == '@':
                        _name = ''
                    else:
                        _name = match.group(1)

                    _type = match.group(3)
                    _ttl = int(match.group(2))
                    _value = match.group(4).strip()

                if _type == 'SOA':
                    continue

                try:
                    if getattr(self, '_data_for_{}'.format(_type)) is not None:

                        if _type not in data:
                            data[_type] = dict()

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
                except AttributeError as error:
                    self.log.debug('skipping {} as not supported', _type)
                    continue


            for _type in data:
                for _name in data[_type]:
                    data_for = getattr(self, '_data_for_{}'.format(_type))

                    record = Record.new(
                        zone,
                        _name,
                        data_for(_type, data[_type][_name]),
                        source=self,
                    )
                    zone.add_record(record, lenient=lenient)


        self.log.debug('populate:   found %s records, exists=%s',
                      len(zone.records) - before, exists)
        return exists


    def _compile_commands(self, action, change):
        commands = []

        record = None

        if action == 'ADD':
            record = change.new

        elif action == 'DELETE':
            record = change.existing

        zone = record.zone
        hostname = remove_trailing_dot(record.fqdn)
        ttl = record.ttl
        _type = record._type

        if hostname == '':
            hostname = '@'
        if _type == 'ALIAS':
            _type = 'ANAME'


        if hasattr(record, 'values'):
            values = record.values
        else:
            values = [record.value]


        base = '{} {} {} {}'.format(action, hostname, ttl, _type)

        if re.match('[A]{1,4}', _type) is not None:
            for value in values:
                commands.append('{} {}'.format(base, value))

        elif _type == 'SSHFP':
            data = values[0].data
            commands.append('{} {} {} {}'.format(
                            base, data['algorithm'], data['fingerprint_type'], data['fingerprint']))

        elif _type == 'SRV':
            data = values[0].data
            commands.append('{} {} {} {} {}'.format(
                            base, data['priority'], data['weight'], data['port'], data['target']))
        
        elif _type == 'MX':
            for value in values:
                data = value.data
                commands.append('{} {} {}'.format(
                                base, data['preference'], data['exchange']))

        else:
            try:
                if getattr(self, '_data_for_{}'.format(_type)) is not None:
                    commands.append('{} {}'.format(
                                    base, values[0]))
            except AttributeError as error:
                self.log.debug('skipping {} as not supported', _type)
                pass

        return commands

    def _apply_Create(self, change):

        pp = pprint.PrettyPrinter(depth=10, stream=sys.stderr)

        zone = change.new.zone
        commands = self._compile_commands('ADD', change)
        pp.pprint(commands)

        for command in commands:
            self._post({
                'domain': remove_trailing_dot(zone.name),
                'origin': '.',
                'password': self._passwords[zone.name],
                'command': command,
            })
            pp.pprint({
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

        pp = pprint.PrettyPrinter(depth=10, stream=sys.stderr)

        zone = change.existing.zone
        commands = self._compile_commands('DELETE', change)
        pp.pprint(commands)

        for command in commands:
            self._post({
                'domain': remove_trailing_dot(zone.name),
                'origin': '.',
                'password': self._passwords[zone.name],
                'command': command,
            })
            pp.pprint({
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

        domain_name = desired.name

        for change in changes:
            class_name = change.__class__.__name__
            getattr(self, '_apply_{}'.format(class_name))(change)

        

