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
from collections import defaultdict

import logging
from functools import reduce
from ..record import Record
from .base import BaseProvider   

TESTING = True

class AkamaiClientException(Exception):
    
    _errorMessages = {
        400: "400: Bad request", 
        403: "403: Access is forbidden",
        404: "404: Resource not found",
        405: "405: Method not supported",
        406: "406: Not Acceptable",
        409: "409: Request not allowed due to conflict with current state of resource",
        415: "415: Unsupported media type",
        422: "422: Request body contains an error preventing processing",
        500: "500: Internal server error"
    }

    def __init__(self, code):
        message = self._errorMessages.get(code)
        super(AkamaiClientException, self).__init__(message)


class _AkamaiRecord(object):
    pass


class AkamaiClient(object):

    def __init__(self, _client_secret, _host, _access_token, _client_token):

        self.base = "https://" + _host + "/config-dns/v2/"
        self.basev1 = "https://" + _host + "/config-dns/v1/"

        sess = requests.Session()
        sess.auth = EdgeGridAuth(
            client_token=_client_token,
            client_secret=_client_secret,
            access_token=_access_token
        )
        self._sess = sess


    def _writePrepped(self, prepped):
        filename = str(prepped.method)  + ".json"
        f = open(filename, 'w')

        f.write("headers: \n")
        f.write(str(prepped.headers))
        f.write("\nbody: \n")
        f.write(str(prepped.body))
        f.write("\nhooks:\n")
        f.write(str(prepped.hooks))
        f.write("\nmethod: " + str(prepped.method))
        f.write("\nurl: " + str(prepped.url) + "\n")
        
        f.close()

    def _request(self, method, path, params=None, data=None, v1=False):
        
        url = urljoin(self.base, path)
        if v1: 
            url = urljoin(self.basev1, path)

        if (TESTING):  
            print("testing mode")
            print(method, url)
            req = requests.Request(method, url, params=params, json=data)
            prepped = req.prepare()
            self._writePrepped(prepped)

        resp = self._sess.request(method, url, params=params, json=data)

        
        if resp.status_code > 299:
            raise AkamaiClientException(resp.status_code)

        resp.raise_for_status()


        return resp    

 
    def record_get(self, zone, name, record_type):
        
        path = 'zones/{}/names/{}/types/{}'.format(zone, name, record_type)
        result = self._request('GET', path)
        
        return result

    def record_create(self, zone, name, record_type, params):
        path = 'zones/{}/names/{}/types/{}'.format(zone, name, record_type)
        result = self._request('POST', path, data=params)

        return result

    def record_delete(self, zone, name, record_type):
        path = 'zones/{}/names/{}/types/{}'.format(zone, name, record_type)
        result = self._request('DELETE', path)
        
        if result.status_code == 204:
            print ("successfully deleted ", path)

        return result

    def record_replace(self, zone, name, record_type, params):
        path = 'zones/{}/names/{}/types/{}'.format(zone, name, record_type)
        result = self._request('PUT', path, data=params)

        return result

    def zones_get(self, contractIds=None, page=None, pageSize=None, search=None,
                     showAll="true", sortBy="zone", types=None):
        path = 'zones'

        params = {
            'contractIds': contractIds,
            'page': page, 
            'pageSize': pageSize,
            'search': search,
            'showAll': showAll,
            'sortBy': sortBy,
            'types': types
        }

        result = self._request('GET', path, params=params)

        return result

    def zone_recordset_get(self, zone, page=None, pageSize=30, search=None,
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

    def records(self, zone_name):
        
        recordset = self.zone_recordset_get(zone_name, showAll="true").json().get("recordsets")

        return recordset

    def master_zone_file_get(self, zone):
        
        path = 'zones/{}/zone-file'.format(zone)

        try:
            result = self._request('GET', path)

        except AkamaiClientException as e:
            # not working with API v2, API v1 fallback
            path = 'zones/{}'.format(zone)
            result = self._request('GET', path, v1=True)
            print("Using API v1 fallback")
            print("(Probably Ignore)", e.message)

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


    def zone_records(self, zone):
        if zone.name not in self._zone_records:
            try:
                self._zone_records[zone.name] = self._dns_client.records(zone.name[:-1])

            except AkamaiClientException:
                return []

        return self._zone_records[zone.name]


    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s, target=%s, lenient=%s', zone.name, target, lenient)
        
        # self._test(zone)

        values = defaultdict(lambda: defaultdict(list))

        for record in self.zone_records(zone):
            _type=record['type']
            if _type not in self.SUPPORTS:
                continue
            elif _type == 'TXT' and record['content'].startswith('ALIAS for'):
                # ALIAS has a "ride along" TXT record with 'ALIAS for XXXX',
                # we're ignoring it
                continue
            values[record['name']][record['type']].append(record)



    def _test(self, zone) :

        zone_name = zone.name[:len(zone.name)-1]

        record_name = "octo.basir-test.com"
        record_type = "A"
        params = {
            "name": "octo.basir-test.com",
            "type": "A",
            "ttl": 300,
            "rdata": [
                "10.0.0.2",
                "10.0.0.3"
            ]
        }
        repl_params = {
            "name": "octo.basir-test.com",
            "type": "A",
            "ttl": 300,
            "rdata": [
                "99.99.99.99",
                "10.0.0.3",
                "1.2.3.4"
            ]
        }


        # print("\n\nRunning test: record get..........\n")
        # self._test_record_get(zone_name, "test.basir-test.com", record_type)
        # print("\n\nRunning test: record create..........\n")
        # self._test_record_create(zone_name, record_name, record_type, params)
        # print("\n\nRunning test: record replace..........\n")
        # self._test_record_replace(zone_name, record_name, record_type, repl_params)
        # print("\n\nRunning test: record delete..........\n")
        # self._test_record_delete(zone_name, record_name, record_type)

        # print("\n\nRunning test: zones get..........\n")
        # self._test_zones_get()

        print("\n\nRunning test: zone recordset get..........\n")
        self._test_zones_recordset_get(zone_name)

        # print("\n\nRunning test: Master Zone File get..........\n")
        # self._test_master_zone_file_get(zone_name)

        return

    def _test_record_get(self, zone_name, record_name, record_type):
        try:
            get = self._dns_client.record_get(zone_name, record_name, record_type)
        except AkamaiClientException as e:
            print ("record get test failed")
            print (e.message)

        else:
            print("record get test result: ")
            print(json.dumps(get.json(), indent=4, separators=(',', ': ')))

        return

    def _test_record_delete(self, zone_name, record_name, record_type):

        try:
            delete = self._dns_client.record_delete(zone_name, record_name, record_type)
        except AkamaiClientException as e:
            print("delete failed")
            print(e.message)
            return


        try:
            self._dns_client.record_get(zone_name, record_name, record_type)
        except AkamaiClientException as e:
            print("get on record failed as expected, since record was succesfully deleted")
            print ("(Probably Ignore):", e.message)
            print ("delete status:", delete.status_code)
        else:
            print("unexpected condition in test delete")

        return

    def _test_record_create(self, zone_name, record_name, record_type, params):

        try:
            create  = self._dns_client.record_create(zone_name, record_name, record_type, params)
        except AkamaiClientException as e:
            print ("create unsuccessful, presumably because it already exists")
            print ("(Probably Ignore)", e.message)
        else:
            print("initial create of", create.json().get("name"), "succesful: ", create.status_code)

        return

    def _test_record_replace(self, zone_name, record_name, record_type, params):

        ## create record to be replaced, if it doesn't already exist
        try:
            old_params = {
                "name": record_name,
                "type": record_type,
                "ttl": 300,
                "rdata": [
                    "10.0.0.2",
                    "10.0.0.3"
                ]
            }
            create = self._dns_client.record_create(zone_name, record_name, record_type, old_params)
        except AkamaiClientException as e:
            print ("initial create unsuccessful, presumably because it already exists")
            print ("(Probably Ignore)", e.message)
        else:
            print("initial create of record to be replaced", create.json().get("name"), "succesful: ", create.status_code)

        
        ## test replace
        try:
            replace = self._dns_client.record_replace(zone_name, record_name, record_type, params)
        except AkamaiClientException as e:
            print("replace failed")
            print(e.message)
            return
        else:
            try:
                record = self._dns_client.record_get(zone_name, record_name, record_type)
            except AkamaiClientException as e:
                print("retrieval in replacement failed")
                print(e.message)
            else:
                new_data = record.json()

                if (new_data != params):
                    print("replace failed, records don't match")
                    print("current data:")
                    print(new_data)
                    print("expected data:")
                    print(params)
                
                else:
                    print("replace succesful")
                    print("replace status:", replace.status_code)

    def _test_zones_get(self):
        try:
            zonesList = self._dns_client.zones_get()
        except AkamaiClientException as e:
            print ("zones get test failed") 
            print (e.message)

        else:
            print("zones list: ")
            print(json.dumps(zonesList.json(), indent=4, separators=(',', ': ')))

        return

    def _test_zones_recordset_get(self, zone_name):
        try:
            zoneRecordset = self._dns_client.zone_recordset_get(zone_name)
        except AkamaiClientException as e:
            print("zone recordset retrieval test failed")
            print (e.message)
        else:
            print("zone recordset: ")
            print(json.dumps(zoneRecordset.json(), indent=4, separators=(',', ': ')))
        return

    def _test_master_zone_file_get(self, zone_name):
        try:
            mzf = self._dns_client.master_zone_file_get(zone_name)

        except AkamaiClientException as e:
            print("MZF retrieval test failed")
            print (e.message)

        else:
            print("Master Zone File:")
            print(json.dumps(mzf.json(), indent=4, separators=(',', ': ')))

        return 
