#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger

logger = getLogger('PowerDns')
try:
    logger.warning('octodns_powerdns shimmed. Update your provider class to '
                   'octodns_powerdns.PowerDnsProvider. '
                   'Shim will be removed in 1.0')
    from octodns_powerdns import PowerDnsProvider, PowerDnsBaseProvider
    PowerDnsProvider  # pragma: no cover
    PowerDnsBaseProvider  # pragma: no cover
except ModuleNotFoundError:
    logger.exception('PowerDnsProvider has been moved into a seperate module, '
                     'octodns_powerdns is now required. Provider class should '
                     'be updated to octodns_powerdns.PowerDnsProvider. See '
                     'https://github.com/octodns/octodns#updating-'
                     'to-use-extracted-providers for more information.')
    raise
