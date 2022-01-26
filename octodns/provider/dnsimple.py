#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger

logger = getLogger('Dnsimple')
try:
    logger.warning('octodns_dnsimple shimmed. Update your provider class to '
                   'octodns_dnsimple.DnsimpleProvider. '
                   'Shim will be removed in 1.0')
    from octodns_dnsimple import DnsimpleProvider
    DnsimpleProvider  # pragma: no cover
except ModuleNotFoundError:
    logger.exception('DnsimpleProvider has been moved into a seperate module, '
                     'octodns_dnsimple is now required. Provider class should '
                     'be updated to octodns_dnsimple.DnsimpleProvider. See '
                     'https://github.com/octodns/octodns#updating-'
                     'to-use-extracted-providers for more information.')
    raise
