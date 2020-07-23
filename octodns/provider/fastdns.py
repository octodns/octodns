#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from .edgedns import AkamaiProvider
from logging import getLogger

# Quell unused warning
AkamaiProvider

log = getLogger('octodns.provider.fastdns.AkamaiProvider')
log.warn('DEPRECATION NOTICE: AkamaiProvider has been moved to '
         'octodns.provider.fastdns.AkamaiProvider')
