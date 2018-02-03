#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from collections import defaultdict
from requests import Session
import logging
from urllib import urlencode
from time import sleep
import time
import json
import re

from ..record import Record
from .base import BaseProvider


class UltraClientException(Exception):
    pass


class UltraClientNotFound(UltraClientException):

    def __init__(self):
        super(UltraClientNotFound, self).__init__('Not Found')


class UltraClientUnauthorized(UltraClientException):

    def __init__(self):
        super(UltraClientUnauthorized, self).__init__('Unauthorized')


class UnknownRdatatype(Exception):
    """DNS resource record type is unknown."""


class UltraClient(object):
    BASE = 'https://restapi.ultradns.com/v2'

    NONE = 0
    A = 1
    NS = 2
    MD = 3
    MF = 4
    CNAME = 5
    SOA = 6
    MB = 7
    MG = 8
    MR = 9
    NULL = 10
    WKS = 11
    PTR = 12
    HINFO = 13
    MINFO = 14
    MX = 15
    TXT = 16
    RP = 17
    AFSDB = 18
    X25 = 19
    ISDN = 20
    RT = 21
    NSAP = 22
    NSAP_PTR = 23
    SIG = 24
    KEY = 25
    PX = 26
    GPOS = 27
    AAAA = 28
    LOC = 29
    NXT = 30
    SRV = 33
    NAPTR = 35
    KX = 36
    CERT = 37
    A6 = 38
    DNAME = 39
    OPT = 41
    APL = 42
    DS = 43
    SSHFP = 44
    IPSECKEY = 45
    RRSIG = 46
    NSEC = 47
    DNSKEY = 48
    DHCID = 49
    NSEC3 = 50
    NSEC3PARAM = 51
    TLSA = 52
    HIP = 55
    CDS = 59
    CDNSKEY = 60
    OPENPGPKEY = 61
    CSYNC = 62
    SPF = 99
    UNSPEC = 103
    EUI48 = 108
    EUI64 = 109
    TKEY = 249
    TSIG = 250
    IXFR = 251
    AXFR = 252
    MAILB = 253
    MAILA = 254
    ANY = 255
    URI = 256
    CAA = 257
    AVC = 258
    TA = 32768
    DLV = 32769

    _by_text = {
        'NONE': NONE,
        'A': A,
        'NS': NS,
        'MD': MD,
        'MF': MF,
        'CNAME': CNAME,
        'SOA': SOA,
        'MB': MB,
        'MG': MG,
        'MR': MR,
        'NULL': NULL,
        'WKS': WKS,
        'PTR': PTR,
        'HINFO': HINFO,
        'MINFO': MINFO,
        'MX': MX,
        'TXT': TXT,
        'RP': RP,
        'AFSDB': AFSDB,
        'X25': X25,
        'ISDN': ISDN,
        'RT': RT,
        'NSAP': NSAP,
        'NSAP-PTR': NSAP_PTR,
        'SIG': SIG,
        'KEY': KEY,
        'PX': PX,
        'GPOS': GPOS,
        'AAAA': AAAA,
        'LOC': LOC,
        'NXT': NXT,
        'SRV': SRV,
        'NAPTR': NAPTR,
        'KX': KX,
        'CERT': CERT,
        'A6': A6,
        'DNAME': DNAME,
        'OPT': OPT,
        'APL': APL,
        'DS': DS,
        'SSHFP': SSHFP,
        'IPSECKEY': IPSECKEY,
        'RRSIG': RRSIG,
        'NSEC': NSEC,
        'DNSKEY': DNSKEY,
        'DHCID': DHCID,
        'NSEC3': NSEC3,
        'NSEC3PARAM': NSEC3PARAM,
        'TLSA': TLSA,
        'HIP': HIP,
        'CDS': CDS,
        'CDNSKEY': CDNSKEY,
        'OPENPGPKEY': OPENPGPKEY,
        'CSYNC': CSYNC,
        'SPF': SPF,
        'UNSPEC': UNSPEC,
        'EUI48': EUI48,
        'EUI64': EUI64,
        'TKEY': TKEY,
        'TSIG': TSIG,
        'IXFR': IXFR,
        'AXFR': AXFR,
        'MAILB': MAILB,
        'MAILA': MAILA,
        'ANY': ANY,
        'URI': URI,
        'CAA': CAA,
        'AVC': AVC,
        'TA': TA,
        'DLV': DLV,
    }
    _unknown_type_pattern = re.compile('TYPE([0-9]+)$', re.I)

    def __init__(self, account_name, username, password, sleep_period):
        self._connected = False
        sess = Session()
        self._sess = sess
        self.token_expires_at = None
        self.account_name = account_name
        self._username = username
        self._password = password
        self.sleep_after_zone_creation = sleep_period

    def _check_ultra_session(self):
        current_time = time.time()
        if not self.token_expires_at:
            self._connect_session()
        elif self.token_expires_at <= current_time:
            self._refresh_auth_token()

    def _refresh_auth_token(self):
        data = {'grant_type': "refresh_token",
                'refresh_token': self.refresh_token}
        self._execute_auth_request(data)

    def _connect_session(self):
        data = {'grant_type': "password", 'username': self._username,
                'password': self._password}
        self._execute_auth_request(data)

    def _execute_auth_request(self, data):
        try:
            url = '{}{}'.format(self.BASE, "/authorization/token")
            resp = self._sess.request("POST", url, data=urlencode(data))
            if resp.status_code == 401:
                raise UltraClientUnauthorized()
            if resp.status_code == 404:
                raise UltraClientNotFound()
            resp.raise_for_status()
        except Exception as e:
            raise UltraClientException(e)

        try:
            json_data = json.loads(resp.content)
            self.refresh_token = json_data['refreshToken']
            self.access_token = json_data['accessToken']
            # Just adding some padding on the expiration to be safe
            self.token_expires_at = time.time() + \
                float(json_data['expiresIn']) - 120
        except KeyError as e:
            raise UltraClientException(e)
        self._sess.headers.update(
            {'Authorization': 'Bearer {}'.format(self.access_token),
             'Content-Type': 'application/json'})

    def _request(self, method, path, params=None, data=None):
        self._check_ultra_session()
        url = '{}{}'.format(self.BASE, path)
        resp = self._sess.request(method, url, params=params, json=data)
        if resp.status_code == 401:
            raise UltraClientUnauthorized()
        if resp.status_code == 404:
            raise UltraClientNotFound()
        resp.raise_for_status()
        return resp

    def from_text(self, text):
        """Convert text into a DNS rdata type value.
        The input text can be a defined DNS RR type mnemonic or
        instance of the DNS generic type syntax.
        For example, "NS" and "TYPE2" will both result in a value of 2.
        Raises ``dns.rdatatype.UnknownRdatatype`` if the type is unknown.
        Raises ``ValueError`` if the rdata type value is not >= 0 and <= 65535.
        Returns an ``int``.
        """

        value = self._by_text.get(text.upper())
        if value is None:
            match = self._unknown_type_pattern.match(text)
            if match is None:
                raise UnknownRdatatype
            value = int(match.group(1))
            if value < 0 or value > 65535:
                raise ValueError("type must be between >= 0 and <= 65535")
        return value

    def format_rrtype_from_text(self, _type):
        return "{} ({})".format(_type.upper(), self.from_text(_type))

    def domain(self, name):
        path = '/zones/{}'.format(name)
        return self._request('GET', path).json()

    def domain_create(self, name):
        data = {
            'properties': {
                'name': name,
                'accountName': self.account_name,
                'type': 'PRIMARY'
            },
            "primaryCreateInfo": {
                "forceImport": True,
                "createType": "NEW"
            }
        }
        self._request('POST', '/zones', data=data)
        # UltraDNS needs a little bit of time after zone
        #      creation before we can request the records
        sleep(self.sleep_after_zone_creation)

    def records(self, zone):
        zone_name = zone.name
        path = '/zones/{}/rrsets'.format(zone_name)
        ret = []

        offset = 0
        limit = 500
        while True:
            data = self._request('GET', path,
                                 {'offset': offset, 'limit': limit}).json()
            ret += data['rrSets']
            # https://ultra-portalstatic.ultradns.com/static/docs/REST-API_User_Guide.pdf
            # pages exists if there is more than 1 page
            # last doesn't exist if you're on the last page
            # "resultInfo":{"totalCount":13,"offset":10,"returnedCount":3}}
            try:
                info = data['resultInfo']
                total_count = int(info['totalCount'])
                info_offset = int(info['offset'])
                returned_count = int(info['returnedCount'])

                if info_offset + returned_count >= total_count:
                    break

                offset += limit
            except KeyError:
                break

        regex = r"([\w]+)\s+\([\d]+\)"
        for record in ret:
            # parse the type and only keep the real type
            # from CNAME (5) to cname
            m = re.match(regex, record['rrtype'])
            record['rrtype'] = m.group(1)
            record['ownerName'] = zone.hostname_from_fqdn(record['ownerName'])

        return ret

    def record_create(self, zone_name, params):
        type_str = params['rrtype']
        params['rrtype'] = self.format_rrtype_from_text(type_str)
        path = '/zones/{}/rrsets/{}/{}'.format(zone_name,
                                               type_str.upper(),
                                               params['ownerName'])
        self._request('POST', path, data=params)

    def record_update(self, zone_name, params):
        type_str = params['rrtype']
        params['rrtype'] = self.format_rrtype_from_text(type_str)
        path = '/zones/{}/rrsets/{}/{}'.format(zone_name,
                                               type_str.upper(),
                                               params['ownerName'])
        self._request('PUT', path, data=params)

    def record_delete(self, zone_name, record):
        path = '/zones/{}/rrsets/{}/{}'.format(zone_name,
                                               record._type.upper(),
                                               record.name)
        self._request('DELETE', path)


class UltraProvider(BaseProvider):
    '''
    Ultra DNS provider using API v2

    ultra:
        class: octodns.provider.ultra.UltraProvider
        # Your ultradns username (required)
        username: user
        # Your ultradns password (required)
        password: pass
    '''
    SUPPORTS_GEO = False
    SUPPORTS = set(('A', 'AAAA', 'CAA', 'CNAME', 'MX', 'NS',
                    'TXT', 'SRV', 'NAPTR', 'SPF'))

    def __init__(self, id, account_name, username, password,
                 sleep_period, *args, **kwargs):
        self.log = logging.getLogger('UltraProvider[{}]'.format(id))
        self.log.debug('__init__: id=%s, token=***', id)
        super(UltraProvider, self).__init__(id, *args, **kwargs)
        self.username = username
        self.password = password
        self.account_name = account_name
        self._client = UltraClient(account_name, username, password,
                                   sleep_period)

        self._zone_records = {}

    def _data_for_multiple(self, _type, records):
        record = records[0]
        return {
            'ttl': record['ttl'],
            'type': _type,
            'values': record['rdata']
        }

    _data_for_A = _data_for_multiple
    _data_for_AAAA = _data_for_multiple
    _data_for_NS = _data_for_multiple

    _fix_semicolons = re.compile(r'(?<!\\);')

    def _data_for_TXT(self, _type, records):
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': [self._fix_semicolons.sub('\;', rr)
                       for rr in records[0]['rdata']]
        }

    _data_for_SPF = _data_for_TXT

    def _data_for_CNAME(self, _type, records):
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'value': records[0]['rdata'][0]
        }

    def _data_for_CAA(self, _type, records):
        values = []
        for record in records:
            flags, tag, value = record['rdata'][0].split(' ')
            values.append({
                'flags': flags,
                'tag': tag,
                'value': value[1:-1],
            })
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': values
        }

    def _data_for_MX(self, _type, records):
        values = []
        for record in records:
            for value in record['rdata']:
                preference, exchange = value.split(' ')
                values.append({
                    'preference': preference,
                    'exchange': exchange,
                })
        return {
            'ttl': records[0]['ttl'],
            'type': _type,
            'values': values
        }

    def _data_for_NAPTR(self, _type, rrset):
        values = []
        for rr in rrset['ResourceRecords']:
            order, preference, flags, service, regexp, replacement = \
                rr['rdata'][0].split(' ')
            flags = flags[1:-1]
            service = service[1:-1]
            regexp = regexp[1:-1]
            values.append({
                'order': order,
                'preference': preference,
                'flags': flags,
                'service': service,
                'regexp': regexp,
                'replacement': replacement,
            })
        return {
            'type': _type,
            'values': values,
            'ttl': int(rrset[0]['ttl'])
        }

    def _data_for_SRV(self, _type, records):
        values = []
        for record in records:
            priority, weight, port, target = record['rdata'][0].split(' ')
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

    def zone_records(self, zone):
        if zone.name not in self._zone_records:
            try:
                self._zone_records[zone.name] = \
                    self._client.records(zone)
            except UltraClientNotFound:
                return []

        return self._zone_records[zone.name]

    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s, target=%s, lenient=%s', zone.name,
                       target, lenient)

        values = defaultdict(lambda: defaultdict(list))
        for record in self.zone_records(zone):
            _type = record['rrtype']
            record_name = record['ownerName']
            values[record_name][_type].append(record)

        before = len(zone.records)
        for name, types in values.items():
            for _type, records in types.items():
                if _type == 'SOA':
                    continue
                data_for = getattr(self, '_data_for_{}'.format(_type))
                record = Record.new(zone, name, data_for(_type, records),
                                    source=self, lenient=lenient)
                zone.add_record(record)

        self.log.info('populate:   found %s records',
                      len(zone.records) - before)

    def _params_for_multiple(self, record):
        yield {
            'ttl': record.ttl,
            'ownerName': record.name,
            'rrtype': record._type,
            'rdata': record.values
        }

    def _params_for_multiple_ips(self, record):
        if len(record.values) > 1:
            yield {
                'ttl': record.ttl,
                'ownerName': record.name,
                'rrtype': record._type,
                'rdata': record.values,
                'profile': {
                    '@context':
                        'http://schemas.ultradns.com/RDPool.jsonschema',
                    'order': 'RANDOM',
                    'description': record.name
                }
            }
        else:
            yield {
                'ttl': record.ttl,
                'ownerName': record.name,
                'rrtype': record._type,
                'rdata': record.values
            }

    _params_for_A = _params_for_multiple_ips
    _params_for_AAAA = _params_for_multiple_ips
    _params_for_NS = _params_for_multiple
    _params_for_SPF = _params_for_multiple

    def _params_for_TXT(self, record):
        yield {
            'ttl': record.ttl,
            'ownerName': record.name,
            'rrtype': record._type,
            'rdata': record.chunked_values
        }

    def _params_for_CAA(self, record):
        yield {
            'ttl': record.ttl,
            'ownerName': record.name,
            'rrtype': record._type,
            'rdata': ['{} {} "{}"'.format(v.flags, v.tag, v.value)
                      for v in record.values]
        }

    def _params_for_single(self, record):
        yield {
            'rdata': [record.value],
            'ownerName': record.name,
            'ttl': record.ttl,
            'rrtype': record._type
        }

    _params_for_CNAME = _params_for_single

    def _params_for_MX(self, record):
        yield {
            'ttl': record.ttl,
            'ownerName': record.name,
            'rrtype': record._type,
            'rdata': ['{} {}'.format(v.preference, v.exchange)
                      for v in record.values]
        }

    def _params_for_SRV(self, record):
        yield {
            'ttl': record.ttl,
            'ownerName': record.name,
            'rrtype': record._type,
            'rdata': ['{} {} {} {}'.format(v.priority, v.weight, v.port,
                                           v.target)
                      for v in record.values]
        }

    def _params_for_NAPTR(self, record):
        yield {
            'ttl': record.ttl,
            'ownerName': record.name,
            'rrtype': record._type,
            'rdata': ['{} {} "{}" "{}" "{}" {}'
                      .format(v.order, v.preference,
                              v.flags if v.flags else '',
                              v.service if v.service else '',
                              v.regexp if v.regexp else '',
                              v.replacement)
                      for v in record.values]
        }

    def _apply_Create(self, change):
        new = change.new
        params_for = getattr(self, '_params_for_{}'.format(new._type))
        for params in params_for(new):
            if params['ownerName'] == '':
                params['ownerName'] = new.zone.name
            self._client.record_create(new.zone.name, params)

    def _apply_Update(self, change):
        new = change.new
        params_for = getattr(self, '_params_for_{}'.format(new._type))
        for params in params_for(new):
            if params['ownerName'] == '':
                params['ownerName'] = new.zone.name
            self._client.record_update(new.zone.name, params)

    def _apply_Delete(self, change):
        existing = change.existing
        zone = existing.zone
        for record in self.zone_records(zone):
            if existing.name == record['ownerName'] and \
               existing._type == record['rrtype']:
                if existing.name == '':
                    existing.name = zone.name
                self._client.record_delete(zone.name, existing)

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        self.log.debug('_apply: zone=%s, len(changes)=%d', desired.name,
                       len(changes))

        domain_name = desired.name
        try:
            self._client.domain(domain_name)
        except UltraClientNotFound:
            self.log.debug('_apply:   no matching zone, creating domain')
            self._client.domain_create(domain_name)

        for change in changes:
            class_name = change.__class__.__name__
            getattr(self, '_apply_{}'.format(class_name))(change)

        # Clear out the cache if any
        self._zone_records.pop(desired.name, None)
