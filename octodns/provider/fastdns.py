#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

## octodns specfic imports:
import requests
from akamai.edgegrid import EdgeGridAuth
from urlparse import urljoin
import json


import logging
from functools import reduce
from ..record import Record
from .base import BaseProvider   


class AkamaiClientException(Exception):
    pass

class AkamaiClientBadRequest(AkamaiClientException): #400
    def __init__(self):
        super(AkamaiClientBadRequest, self).__init__('Bad request')

class AkamaiClientNotAuthorized(AkamaiClientException): #403
    def __init__(self):
        super(AkamaiClientNotAuthorized, self).__init__('Forbidden')

class AkamaiClientNotFound(AkamaiClientException): #404
    def __init__(self):
        super(AkamaiClientNotFound, self).__init__('Not found')

class AkamaiClientNotAcceptable(AkamaiClientException): #406
    def __init__(self):
        super(AkamaiClientNotAcceptable, self).__init__('Not acceptable')

class AkamaiClientGenericExcp(AkamaiClientException):
    def __init__(self, num):
        super(AkamaiClientGenericExcp, self).__init__('HTTP Error: ' + str(num))         


class _AkamaiRecord(object):
    pass


class AkamaiClient(object):

    def __init__(self, _client_secret, _host, _access_token, _client_token):

        self.base = "https://" + _host + "/config-dns/v2/zones/"
        self.basev1 = "https://" + _host + "/config-dns/v1/zones/"

        sess = requests.Session()
        sess.auth = EdgeGridAuth(
            client_token=_client_token,
            client_secret=_client_secret,
            access_token=_access_token
        )
        self._sess = sess
        
    def _request(self, method, path, params=None, data=None):
        # url = '{}{}'.format(self.base, path)
        url = urljoin(self.base, path)
        print(url)
        resp = self._sess.request(method, url, params=params, json=data)

        if resp.status_code == 400:
            raise AkamaiClientBadRequest()
        if resp.status_code == 403:
            raise AkamaiClientNotAuthorized()
        if resp.status_code == 404:
            raise AkamaiClientNotFound()
        if resp.status_code == 406:
            raise AkamaiClientNotAcceptable()
        resp.raise_for_status()

        return resp    


    # def getZone(self, name):
    #     path = name + "/recordsets/"        
    #     result = self._request('GET', path, "sortBy=type&types=A")

    #     return result.json()

    # def getNames(self, name):
    #     path = name + "/names/"
    #     result = self._request('GET', path)

    #     return result.json()



    def record_get(self, zone, name, record_type):
        
        path = '/zones/{}/names/{}/types/'.format(zone, name, record_type)
        result = self._request('GET', path)
        
        return result.json()

    def record_create(self, zone, name, record_type, params):
        path = '/zones/{}/names/{}/types/'.format(zone, name, record_type)
        result = self._request('POST', path, data=params)

        return result


    def record_delete(self, zone, name, record_type):
        path = '/zones/{}/names/{}/types/'.format(zone, name, record_type)
        result = self._request('DELETE', path)
        
        return result

    def record_replace(self, zone, name, record_type, params):
        path = '/zones/{}/names/{}/types/'.format(zone, name, record_type)
        result = self._request('PUT', path, data=params)

        return result

class AkamaiProvider(BaseProvider):

    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS = set(('A', 'AAAA', 'CNAME', 'MX', 'NAPTR', 'NS', 'PTR', 'SPF', 
                    'SRV', 'SSHFP', 'TXT'))

                    
    def __init__(self, id, client_secret, host, access_token, client_token, 
                *args, **kwargs):
        
        self.log = logging.getLogger('AkamaiProvider[{}]'.format(id))
        self.log.debug('__init__: id=%s, ')
        super(AkamaiProvider, self).__init__(id, *args, **kwargs)


        self._dns_client = AkamaiClient(client_secret, host, access_token, client_token)
        

        self._zone_records = {}



    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s, target=%s, lenient=%s', zone.name, target, lenient)


        zone_name = zone.name[:len(zone.name)-1]
        zone = self._dns_client.getZone(zone_name)
        names = self._dns_client.getNames(zone_name)


        #  print(type(result))
        #print(result.text)

        zoneFile = open('zoneFile.json', 'w')
        namesFile = open('namesFile.json', 'w')
        zoneFile.write(json.dumps(zone, indent=4, separators=(',', ': ')))
        namesFile.write(json.dumps(names, indent=4, separators=(',', ': ')))
        zoneFile.close()
        namesFile.close()



        #print (json.dumps(result, indent=4, separators=(',', ': ')))

        return




