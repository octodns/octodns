#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

## octodns specfic imports:

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

        ## generate edgegrid
        #### create credential file, and write credentials to it
        credFile = open('tempCred.txt', 'w')

        credFile.write('client_secret = ')
        credFile.write(str(client_secret))
        credFile.write('\n\n')

        credFile.write('host = %s', str(host))
        credFile.write('\n\n')

        credFile.write('access_token = %s', str(access_token))
        credFile.write('\n\n')
        
        credFile.write('client_token = %s', str(client_token))

        credFile.close()
         
        #### generate edgegrid using tool

        #### delete temp txt file 