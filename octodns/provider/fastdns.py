#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

## octodns specfic imports:
from os.path import expanduser
import ConfigParser

# import os ## command line workaround


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


    def _authenticate(self, client_secret, host, access_token, client_token):

        # ## generate edgegrid
        # section_name = "dns"
        # home = expanduser("~")
        # index = 0 
        # fields = {}

        # ## process original .edgerc file
        # origConfig = ConfigParser.ConfigParser()
        # filename = "%s/.edgerc" % home
        
        # # If this is a new file, create it
        # if not os.path.isfile(filename):
        #     open(filename, 'a+').close()
            
        # origConfig.read(filename)

        # ## credential type already exists, prompt to overwrite
        # if section_name in origConfig.sections():
        #     print (">>> Replacing section: %s" % section_name)
        #     sys.stdout.write ("*** OK TO REPLACE section %s? *** [Y|n]:" % section_name)
        #     real_raw_input = vars(__builtins__).get('raw_input',input)
        #     choice = real_raw_input().lower()
        #     if choice == "n":
        #         print ("Not replacing section.")
        #         return
        #     replace_section = True
        # else:
        #     print ("+++ Creating section: %s" % section_name)
        #     replace_section = False

        # ## open the ~/.edgerc file for writing
        # Config = ConfigParser.ConfigParser()
        # Config.read(filename)
        # confile = open(filename, 'w')


        # ## add  the new section
        


        #### create credential file, and write credentials to it


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
        pass


