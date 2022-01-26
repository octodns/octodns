#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger

logger = getLogger('Akamai')
logger.warning('AkamaiProvider has been moved into a seperate module, '
               'octodns_edgedns is now required. Provider class should '
               'be updated to octodns_edgedns.AkamaiProvider. See '
               'https://github.com/octodns/octodns#updating-'
               'to-use-extracted-providers for more information.')
