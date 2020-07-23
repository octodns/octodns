#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from requests import Session
from akamai.edgegrid import EdgeGridAuth
from six.moves.urllib.parse import urljoin
from collections import defaultdict

from logging import getLogger
from ..record import Record
from .base import BaseProvider


class AkamaiClientNotFound(Exception):

    def __init__(self, resp):
        message = "404: Resource not found"
        super(AkamaiClientNotFound, self).__init__(message)


class AkamaiClient(object):
    '''
    Client for making calls to Akamai Fast DNS API using Python Requests

    Edge DNS Zone Management API V2, found here:
    https://developer.akamai.com/api/cloud_security/edge_dns_zone_management/v2.html

    Info on Python Requests library:
    https://2.python-requests.org/en/master/

    '''

    def __init__(self, client_secret, host, access_token, client_token):

        self.base = "https://" + host + "/config-dns/v2/"

        sess = Session()
        sess.auth = EdgeGridAuth(
            client_token=client_token,
            client_secret=client_secret,
            access_token=access_token
        )
        self._sess = sess

    def _request(self, method, path, params=None, data=None, v1=False):

        url = urljoin(self.base, path)
        resp = self._sess.request(method, url, params=params, json=data)

        if resp.status_code == 404:
            raise AkamaiClientNotFound(resp)
        resp.raise_for_status()

        return resp

    def record_create(self, zone, name, record_type, content):
        path = 'zones/{}/names/{}/types/{}'.format(zone, name, record_type)
        result = self._request('POST', path, data=content)

        return result

    def record_delete(self, zone, name, record_type):
        path = 'zones/{}/names/{}/types/{}'.format(zone, name, record_type)
        result = self._request('DELETE', path)

        return result

    def record_replace(self, zone, name, record_type, content):
        path = 'zones/{}/names/{}/types/{}'.format(zone, name, record_type)
        result = self._request('PUT', path, data=content)

        return result

    def zone_get(self, zone):
        path = 'zones/{}'.format(zone)
        result = self._request('GET', path)

        return result

    def zone_create(self, contractId, params, gid=None):
        path = 'zones?contractId={}'.format(contractId)

        if gid is not None:
            path += '&gid={}'.format(gid)

        result = self._request('POST', path, data=params)

        return result

    def zone_recordset_get(self, zone, page=None, pageSize=None, search=None,
                           showAll="true", sortBy="name", types=None):

        params = {
            'page': page,
            'pageSize': pageSize,
            'search': search,
            'showAll': showAll,
            'sortBy': sortBy,
            'types': types
        }

        path = 'zones/{}/recordsets'.format(zone)
        result = self._request('GET', path, params=params)

        return result


class AkamaiProvider(BaseProvider):

    '''
    Akamai Edge DNS Provider

    edgedns.py:

        Example config file with variables:
            "
            ---
            providers:
              config:
                class: octodns.provider.yaml.YamlProvider
                directory: ./config (example path to directory of zone files)
              edgedns:
                class: octodns.provider.edgedns.AkamaiProvider
                client_secret: env/AKAMAI_CLIENT_SECRET
                host: env/AKAMAI_HOST
                access_token: env/AKAMAI_ACCESS_TOKEN
                client_token: env/AKAMAI_CLIENT_TOKEN
                contract_id: env/AKAMAI_CONTRACT_ID (optional)

            zones:
              example.com.:
                sources:
                  - config
                targets:
                  - edgedns
            "

        The first four variables above can be hidden in environment variables
        and octoDNS will automatically search for them in the shell. It is
        possible to also hard-code into the config file: eg, contract_id.

        The first four values can be found by generating credentials:
        https://control.akamai.com/
        Configure > Organization > Manage APIs > New API Client for me
        Select appropriate group, and fill relevant fields.
        For API Service Name, select DNS-Zone Record Management
        and then set appropriate Access level (Read-Write to make changes).
        Then select the "New Credential" button to generate values for above

        The contract_id paramater is optional, and only required for creating
        a new zone. If the zone being managed already exists in Akamai for the
        user in question, then this paramater is not needed.

    '''

    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False

    SUPPORTS = set(('A', 'AAAA', 'CNAME', 'MX', 'NAPTR', 'NS', 'PTR', 'SPF',
                    'SRV', 'SSHFP', 'TXT'))

    def __init__(self, id, client_secret, host, access_token, client_token,
                 contract_id=None, gid=None, *args, **kwargs):

        self.log = getLogger('AkamaiProvider[{}]'.format(id))
        self.log.debug('__init__: id=%s, ')
        super(AkamaiProvider, self).__init__(id, *args, **kwargs)

        self._dns_client = AkamaiClient(client_secret, host, access_token,
                                        client_token)

        self._zone_records = {}
        self._contractId = contract_id
        self._gid = gid

    def zone_records(self, zone):
        """ returns records for a zone, looks for it if not present, or
            returns empty [] if can't find a match
        """
        if zone.name not in self._zone_records:
            try:
                name = zone.name[:-1]
                response = self._dns_client.zone_recordset_get(name)
                self._zone_records[zone.name] = response.json()["recordsets"]

            except (AkamaiClientNotFound, KeyError):
                return []

        return self._zone_records[zone.name]

    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s', zone.name)

        values = defaultdict(lambda: defaultdict(list))
        for record in self.zone_records(zone):

            _type = record.get('type')
            # Akamai sends down prefix.zonename., while octodns expects prefix
            _name = record.get('name').split("." + zone.name[:-1], 1)[0]
            if _name == zone.name[:-1]:
                _name = ''  # root / @

            if _type not in self.SUPPORTS:
                continue
            values[_name][_type].append(record)

        before = len(zone.records)
        for name, types in values.items():
            for _type, records in types.items():
                data_for = getattr(self, '_data_for_{}'.format(_type))
                record = Record.new(zone, name, data_for(_type, records[0]),
                                    source=self, lenient=lenient)
                zone.add_record(record, lenient=lenient)

        exists = zone.name in self._zone_records
        found = len(zone.records) - before
        self.log.info('populate:   found %s records, exists=%s', found, exists)

        return exists

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        self.log.debug('apply: zone=%s, chnges=%d', desired.name, len(changes))

        zone_name = desired.name[:-1]
        try:
            self._dns_client.zone_get(zone_name)

        except AkamaiClientNotFound:
            self.log.info("zone not found, creating zone")
            params = self._build_zone_config(zone_name)
            self._dns_client.zone_create(self._contractId, params, self._gid)

        for change in changes:
            class_name = change.__class__.__name__
            getattr(self, '_apply_{}'.format(class_name))(change)

        # Clear out the cache if any
        self._zone_records.pop(desired.name, None)

    def _apply_Create(self, change):

        new = change.new
        record_type = new._type

        params_for = getattr(self, '_params_for_{}'.format(record_type))
        values = self._get_values(new.data)
        rdata = params_for(values)

        zone = new.zone.name[:-1]
        name = self._set_full_name(new.name, zone)

        content = {
            "name": name,
            "type": record_type,
            "ttl": new.ttl,
            "rdata": rdata
        }

        self._dns_client.record_create(zone, name, record_type, content)

        return

    def _apply_Delete(self, change):

        zone = change.existing.zone.name[:-1]
        name = self._set_full_name(change.existing.name, zone)
        record_type = change.existing._type

        self._dns_client.record_delete(zone, name, record_type)

        return

    def _apply_Update(self, change):

        new = change.new
        record_type = new._type

        params_for = getattr(self, '_params_for_{}'.format(record_type))
        values = self._get_values(new.data)
        rdata = params_for(values)

        zone = new.zone.name[:-1]
        name = self._set_full_name(new.name, zone)

        content = {
            "name": name,
            "type": record_type,
            "ttl": new.ttl,
            "rdata": rdata
        }

        self._dns_client.record_replace(zone, name, record_type, content)

        return

    def _data_for_multiple(self, _type, records):

        return {
            'ttl': records['ttl'],
            'type': _type,
            'values': [r for r in records['rdata']]
        }

    _data_for_A = _data_for_multiple
    _data_for_AAAA = _data_for_multiple
    _data_for_NS = _data_for_multiple
    _data_for_SPF = _data_for_multiple

    def _data_for_CNAME(self, _type, records):
        value = records['rdata'][0]
        if (value[-1] != '.'):
            value = '{}.'.format(value)

        return {
            'ttl': records['ttl'],
            'type': _type,
            'value': value
        }

    def _data_for_MX(self, _type, records):
        values = []
        for r in records['rdata']:
            preference, exchange = r.split(" ", 1)
            values.append({
                'preference': preference,
                'exchange': exchange
            })
        return {
            'ttl': records['ttl'],
            'type': _type,
            'values': values
        }

    def _data_for_NAPTR(self, _type, records):
        values = []
        for r in records['rdata']:
            order, preference, flags, service, regexp, repl = r.split(' ', 5)

            values.append({
                'flags': flags[1:-1],
                'order': order,
                'preference': preference,
                'regexp': regexp[1:-1],
                'replacement': repl,
                'service': service[1:-1]
            })
        return {
            'type': _type,
            'ttl': records['ttl'],
            'values': values
        }

    def _data_for_PTR(self, _type, records):

        return {
            'ttl': records['ttl'],
            'type': _type,
            'value': records['rdata'][0]
        }

    def _data_for_SRV(self, _type, records):
        values = []
        for r in records['rdata']:
            priority, weight, port, target = r.split(' ', 3)
            values.append({
                'port': port,
                'priority': priority,
                'target': target,
                'weight': weight
            })

        return {
            'type': _type,
            'ttl': records['ttl'],
            'values': values
        }

    def _data_for_SSHFP(self, _type, records):
        values = []
        for r in records['rdata']:
            algorithm, fp_type, fingerprint = r.split(' ', 2)
            values.append({
                'algorithm': algorithm,
                'fingerprint': fingerprint.lower(),
                'fingerprint_type': fp_type
            })

        return {
            'type': _type,
            'ttl': records['ttl'],
            'values': values
        }

    def _data_for_TXT(self, _type, records):
        values = []
        for r in records['rdata']:
            r = r[1:-1]
            values.append(r.replace(';', '\\;'))

        return {
            'ttl': records['ttl'],
            'type': _type,
            'values': values
        }

    def _params_for_multiple(self, values):
        return [r for r in values]

    def _params_for_single(self, values):
        return values

    _params_for_A = _params_for_multiple
    _params_for_AAAA = _params_for_multiple
    _params_for_NS = _params_for_multiple

    _params_for_CNAME = _params_for_single
    _params_for_PTR = _params_for_single

    def _params_for_MX(self, values):
        rdata = []

        for r in values:
            preference = r['preference']
            exchange = r['exchange']

            record = '{} {}'.format(preference, exchange)
            rdata.append(record)

        return rdata

    def _params_for_NAPTR(self, values):
        rdata = []

        for r in values:
            ordr = r['order']
            prf = r['preference']
            flg = "\"" + r['flags'] + "\""
            srvc = "\"" + r['service'] + "\""
            rgx = "\"" + r['regexp'] + "\""
            rpl = r['replacement']

            record = '{} {} {} {} {} {}'.format(ordr, prf, flg, srvc, rgx, rpl)
            rdata.append(record)

        return rdata

    def _params_for_SPF(self, values):
        rdata = []

        for r in values:
            txt = "\"" + r.replace('\\;', ';') + "\""
            rdata.append(txt)

        return rdata

    def _params_for_SRV(self, values):
        rdata = []
        for r in values:
            priority = r['priority']
            weight = r['weight']
            port = r['port']
            target = r['target']

            record = '{} {} {} {}'.format(priority, weight, port, target)
            rdata.append(record)

        return rdata

    def _params_for_SSHFP(self, values):
        rdata = []
        for r in values:
            algorithm = r['algorithm']
            fp_type = r['fingerprint_type']
            fp = r['fingerprint']

            record = '{} {} {}'.format(algorithm, fp_type, fp)
            rdata.append(record)

        return rdata

    def _params_for_TXT(self, values):
        rdata = []

        for r in values:
            txt = "\"" + r.replace('\\;', ';') + "\""
            rdata.append(txt)

        return rdata

    def _build_zone_config(self, zone, _type="primary", comment=None,
                           masters=[]):

        if self._contractId is None:
            raise NameError("contractId not specified to create zone")

        return {
            "zone": zone,
            "type": _type,
            "comment": comment,
            "masters": masters
        }

    def _get_values(self, data):

        try:
            vals = data['values']
        except KeyError:
            vals = [data['value']]

        return vals

    def _set_full_name(self, name, zone):
        name = name + '.' + zone

        # octodns's name for root is ''
        if (name[0] == '.'):
            name = name[1:]

        return name
