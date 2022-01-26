#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger

logger = getLogger('EasyDns')
try:
    logger.warning('octodns_easydns shimmed. Update your provider class to '
                   'octodns_easydns.EasyDnsProvider. '
                   'Shim will be removed in 1.0')
    from octodns_easydns import EasyDnsProvider, EasyDNSProvider
    EasyDnsProvider  # pragma: no cover
    EasyDNSProvider  # pragma: no cover
except ModuleNotFoundError:
    logger.exception('EasyDNSProvider has been moved into a seperate module, '
                     'octodns_easydns is now required. Provider class should '
                     'be updated to octodns_easydns.EasyDnsProvider. See '
                     'https://github.com/octodns/octodns#updating-'
                     'to-use-extracted-providers for more information.')
    raise
