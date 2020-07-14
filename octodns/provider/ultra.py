from collections import defaultdict
from ipaddress import ip_address
from logging import getLogger
from requests import Session

from ..record import Record
from .base import BaseProvider


class UltraClientException(Exception):
    '''
    Base Ultra exception type
    '''
    pass


class UltraNoZonesExistException(UltraClientException):
    '''
    Specially handling this condition where no zones exist in an account.
    This is not an error exactly yet ultra treats this scenario as though a
    failure has occurred.
    '''
    def __init__(self, data):
        super(UltraNoZonesExistException, self).__init__('NoZonesExist')


class UltraClientUnauthorized(UltraClientException):
    '''
    Exception for invalid credentials.
    '''
    def __init__(self):
        super(UltraClientUnauthorized, self).__init__('Unauthorized')


class UltraProvider(BaseProvider):
    '''
    Neustar UltraDNS provider

    Documentation for Ultra REST API requires a login:
    https://portal.ultradns.com/static/docs/REST-API_User_Guide.pdf
    Implemented to the May 20, 2020 version of the document (dated on page ii)
    Also described as Version 2.83.0 (title page)

    Tested against 3.0.0-20200627220036.81047f5
    As determined by querying https://api.ultradns.com/version

    ultra:
        class: octodns.provider.ultra.UltraProvider
        # Ultra Account Name (required)
        account: acct
        # Ultra username (required)
        username: user
        # Ultra password (required)
        password: pass
    '''

    RECORDS_TO_TYPE = {
        'A (1)': 'A',
        'AAAA (28)': 'AAAA',
        'CAA (257)': 'CAA',
        'CNAME (5)': 'CNAME',
        'MX (15)': 'MX',
        'NS (2)': 'NS',
        'PTR (12)': 'PTR',
        'SPF (99)': 'SPF',
        'SRV (33)': 'SRV',
        'TXT (16)': 'TXT',
    }
    TYPE_TO_RECORDS = {v: k for k, v in RECORDS_TO_TYPE.items()}
    SUPPORTS = set(TYPE_TO_RECORDS.keys())

    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    TIMEOUT = 5

    def _request(self, method, path, params=None,
                 data=None, json=None, json_response=True):
        self.log.debug('_request: method=%s, path=%s', method, path)

        url = '{}{}'.format(self._base_uri, path)
        resp = self._sess.request(method,
                                  url,
                                  params=params,
                                  data=data,
                                  json=json,
                                  timeout=self._timeout)
        self.log.debug('_request:   status=%d', resp.status_code)

        if resp.status_code == 401:
            raise UltraClientUnauthorized()

        if json_response:
            payload = resp.json()

            # Expected return value when no zones exist in an account
            if resp.status_code == 404 and len(payload) == 1 and \
               payload[0]['errorCode'] == 70002:
                raise UltraNoZonesExistException(resp)
        else:
            payload = resp.text
        resp.raise_for_status()
        return payload

    def _get(self, path, **kwargs):
        return self._request('GET', path, **kwargs)

    def _post(self, path, **kwargs):
        return self._request('POST', path, **kwargs)

    def _delete(self, path, **kwargs):
        return self._request('DELETE', path, **kwargs)

    def _put(self, path, **kwargs):
        return self._request('PUT', path, **kwargs)

    def _login(self, username, password):
        '''
        Get an authorization token by logging in using the provided credentials
        '''
        path = '/v2/authorization/token'
        data = {
            'grant_type': 'password',
            'username': username,
            'password': password
        }

        resp = self._post(path, data=data)
        self._sess.headers.update({
            'Authorization': 'Bearer {}'.format(resp['access_token']),
        })

    def __init__(self, id, account, username, password, timeout=TIMEOUT,
                 *args, **kwargs):
        self.log = getLogger('UltraProvider[{}]'.format(id))
        self.log.debug('__init__: id=%s, account=%s, username=%s, '
                       'password=***', id, account, username)

        super(UltraProvider, self).__init__(id, *args, **kwargs)

        self._base_uri = 'https://restapi.ultradns.com'
        self._sess = Session()
        self._account = account
        self._timeout = timeout

        self._login(username, password)

        self._zones = None
        self._zone_records = {}

    @property
    def zones(self):
        if self._zones is None:
            offset = 0
            limit = 100
            zones = []
            paging = True
            while paging:
                data = {'limit': limit, 'q': 'zone_type:PRIMARY',
                        'offset': offset}
                try:
                    resp = self._get('/v2/zones', params=data)
                except UltraNoZonesExistException:
                    paging = False
                    continue

                zones.extend(resp['zones'])
                info = resp['resultInfo']

                if info['offset'] + info['returnedCount'] < info['totalCount']:
                    offset += info['returnedCount']
                else:
                    paging = False

            self._zones = [z['properties']['name'] for z in zones]

        return self._zones

    def _data_for_multiple(self, _type, records):
        return {
            'ttl': records['ttl'],
            'type': _type,
            'values': records['rdata'],
        }

    _data_for_A = _data_for_multiple
    _data_for_SPF = _data_for_multiple
    _data_for_NS = _data_for_multiple

    def _data_for_TXT(self, _type, records):
        return {
            'ttl': records['ttl'],
            'type': _type,
            'values': [r.replace(';', '\\;') for r in records['rdata']],
        }

    def _data_for_AAAA(self, _type, records):
        for i, v in enumerate(records['rdata']):
            records['rdata'][i] = str(ip_address(v))
        return {
            'ttl': records['ttl'],
            'type': _type,
            'values': records['rdata'],
        }

    def _data_for_single(self, _type, record):
        return {
            'type': _type,
            'ttl': record['ttl'],
            'value': record['rdata'][0],
        }

    _data_for_PTR = _data_for_single
    _data_for_CNAME = _data_for_single

    def _data_for_CAA(self, _type, records):
        return {
            'type': _type,
            'ttl': records['ttl'],
            'values': [{'flags': x.split()[0],
                        'tag': x.split()[1],
                        'value': x.split()[2].strip('"')}
                       for x in records['rdata']]
        }

    def _data_for_MX(self, _type, records):
        return {
            'type': _type,
            'ttl': records['ttl'],
            'values': [{'preference': x.split()[0],
                        'exchange': x.split()[1]}
                       for x in records['rdata']]
        }

    def _data_for_SRV(self, _type, records):
        return {
            'type': _type,
            'ttl': records['ttl'],
            'values': [{
                'priority': x.split()[0],
                'weight': x.split()[1],
                'port': x.split()[2],
                'target': x.split()[3],
            } for x in records['rdata']]
        }

    def zone_records(self, zone):
        if zone.name not in self._zone_records:
            if zone.name not in self.zones:
                return []

            records = []
            path = '/v2/zones/{}/rrsets'.format(zone.name)
            offset = 0
            limit = 100
            paging = True
            while paging:
                resp = self._get(path,
                                 params={'offset': offset, 'limit': limit})
                records.extend(resp['rrSets'])
                info = resp['resultInfo']

                if info['offset'] + info['returnedCount'] < info['totalCount']:
                    offset += info['returnedCount']
                else:
                    paging = False

            self._zone_records[zone.name] = records
        return self._zone_records[zone.name]

    def _record_for(self, zone, name, _type, records, lenient):
        data_for = getattr(self, '_data_for_{}'.format(_type))
        data = data_for(_type, records)
        record = Record.new(zone, name, data, source=self, lenient=lenient)
        return record

    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s, target=%s, lenient=%s', zone.name,
                       target, lenient)

        exists = False
        before = len(zone.records)
        records = self.zone_records(zone)
        if records:
            exists = True
            values = defaultdict(lambda: defaultdict(None))
            for record in records:
                name = zone.hostname_from_fqdn(record['ownerName'])
                if record['rrtype'] == 'SOA (6)':
                    continue
                _type = self.RECORDS_TO_TYPE[record['rrtype']]
                values[name][_type] = record

            for name, types in values.items():
                for _type, records in types.items():
                    record = self._record_for(zone, name, _type, records,
                                              lenient)
                    zone.add_record(record, lenient=lenient)

        self.log.info('populate:   found %s records, exists=%s',
                      len(zone.records) - before, exists)
        return exists

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        self.log.debug('_apply: zone=%s, len(changes)=%d', desired.name,
                       len(changes))

        name = desired.name
        if name not in self.zones:
            self.log.debug('_apply:   no matching zone, creating')
            data = {'properties': {'name': name,
                                   'accountName': self._account,
                                   'type': 'PRIMARY'},
                    'primaryCreateInfo': {
                        'createType': 'NEW'}}
            self._post('/v2/zones', json=data)
            self.zones.append(name)
            self._zone_records[name] = {}

        for change in changes:
            class_name = change.__class__.__name__
            getattr(self, '_apply_{}'.format(class_name))(change)

        # Clear the cache
        self._zone_records.pop(name, None)

    def _contents_for_multiple_resource_distribution(self, record):
        if len(record.values) > 1:
            return {
                'ttl': record.ttl,
                'rdata': record.values,
                'profile': {
                    '@context':
                        'http://schemas.ultradns.com/RDPool.jsonschema',
                    'order': 'FIXED',
                    'description': record.fqdn
                }
            }

        return {
            'ttl': record.ttl,
            'rdata': record.values
        }

    _contents_for_A = _contents_for_multiple_resource_distribution
    _contents_for_AAAA = _contents_for_multiple_resource_distribution

    def _contents_for_multiple(self, record):
        return {
            'ttl': record.ttl,
            'rdata': record.values
        }

    _contents_for_NS = _contents_for_multiple
    _contents_for_SPF = _contents_for_multiple

    def _contents_for_TXT(self, record):
        return {
            'ttl': record.ttl,
            'rdata': [v.replace('\\;', ';') for v in record.values]
        }

    def _contents_for_CNAME(self, record):
        return {
            'ttl': record.ttl,
            'rdata': [record.value]
        }

    _contents_for_PTR = _contents_for_CNAME

    def _contents_for_SRV(self, record):
        return {
            'ttl': record.ttl,
            'rdata': ['{} {} {} {}'.format(x.priority,
                                           x.weight,
                                           x.port,
                                           x.target) for x in record.values]
        }

    def _contents_for_CAA(self, record):
        return {
            'ttl': record.ttl,
            'rdata': ['{} {} {}'.format(x.flags,
                                        x.tag,
                                        x.value) for x in record.values]
        }

    def _contents_for_MX(self, record):
        return {
            'ttl': record.ttl,
            'rdata': ['{} {}'.format(x.preference,
                                     x.exchange) for x in record.values]
        }

    def _gen_data(self, record):
        zone_name = self._remove_prefix(record.fqdn, record.name + '.')
        path = '/v2/zones/{}/rrsets/{}/{}'.format(zone_name,
                                                  record._type,
                                                  record.fqdn)
        contents_for = getattr(self, '_contents_for_{}'.format(record._type))
        return path, contents_for(record)

    def _apply_Create(self, change):
        new = change.new
        self.log.debug("_apply_Create:  name=%s type=%s ttl=%s",
                       new.name,
                       new._type,
                       new.ttl)

        path, content = self._gen_data(new)
        self._post(path, json=content)

    def _apply_Update(self, change):
        new = change.new
        self.log.debug("_apply_Update:  name=%s type=%s ttl=%s",
                       new.name,
                       new._type,
                       new.ttl)

        path, content = self._gen_data(new)
        self.log.debug(path)
        self.log.debug(content)
        self._put(path, json=content)

    def _remove_prefix(self, text, prefix):
        if text.startswith(prefix):
            return text[len(prefix):]
        return text

    def _apply_Delete(self, change):
        existing = change.existing

        for record in self.zone_records(existing.zone):
            if record['rrtype'] == 'SOA (6)':
                continue
            if existing.fqdn == record['ownerName'] and \
               existing._type == self.RECORDS_TO_TYPE[record['rrtype']]:
                zone_name = self._remove_prefix(existing.fqdn,
                                                existing.name + '.')
                path = '/v2/zones/{}/rrsets/{}/{}'.format(zone_name,
                                                          existing._type,
                                                          existing.fqdn)
                self._delete(path, json_response=False)
