#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

## octodns specfic imports:
from os.path import expanduser
import requests
from akamai.edgegrid import EdgeGridAuth
from urlparse import urljoin


import logging
from functools import reduce
from ..record import Record
from .base import BaseProvider   


class _AkamaiRecord(object):
    pass




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

        self._authenticate(client_secret, host, access_token, client_token)
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
         self.log.debug('populate: name=%s, target=%s, lenient=%s', zone.name,
                       target, lenient)

        print ("populate(%s)", zone.name)



