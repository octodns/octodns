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


class _AkamaiRecord(object):
    pass


class AkamaiClient(object):

    def __init__(self, _client_secret, _host, _access_token, _client_token):

        self.base = "https://" + _host + "/config-dns/v1/zones/"

        sess = requests.Session()
        sess.auth = EdgeGridAuth(
            client_token=_client_token,
            client_secret=_client_secret,
            access_token=_access_token
        )
        self._sess = sess
        

    def getZone(self, name):
        path = urljoin(self.base, name)
        result = self._sess.get(path)

        return result.json()
        # return result



class AkamaiProvider(BaseProvider):

    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS = set(('A', 'AAAA', 'CAA', 'CNAME', 'MX', 'NS', 'PTR', 'SRV',
                    'TXT'))

                    
    def __init__(self, id, client_secret, host, access_token, client_token, 
                *args, **kwargs):
        
        self.log = logging.getLogger('AkamaiProvider[{}]'.format(id))
        self.log.debug('__init__: id=%s, ')
        super(AkamaiProvider, self).__init__(id, *args, **kwargs)


        self._dns_client = AkamaiClient(client_secret, host, access_token, client_token)
        
        #self._authenticate(client_secret, host, access_token, client_token)
        self._zone_records = {}





    def _authenticate(self, client_secret, host, access_token, client_token):

        ## generate edgegrid
        home = expanduser("~")
        filename = "%s/.edgerc" % home
        with open(filename, 'a') as credFile:

            credFile.write('[dns]\n')

            credFile.write('client_secret = ' + str(client_secret) + '\n')
            credFile.write('host = ' + str(host) + '\n')
            credFile.write('access_token = ' + str(access_token) + '\n')
            credFile.write('client_token = ' + str(client_token) + '\n')
            credFile.close()

    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s, target=%s, lenient=%s', zone.name, target, lenient)


        zone_name = zone.name[:len(zone.name)-1]
        result = self._dns_client.getZone(zone_name)

        
        print()
        print()

        print(type(result))
        #print(result.text)

        print (json.dumps(result, indent=4, separators=(',', ': ')))
        print ("\n\n")

        return




