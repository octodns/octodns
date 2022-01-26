#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger

logger = getLogger('EtcHosts')
try:
    logger.warning('octodns_etchosts shimmed. Update your provider class to '
                   'octodns_etchosts.EtcHostsProvider. '
                   'Shim will be removed in 1.0')
    from octodns_etchosts import EtcHostsProvider
    EtcHostsProvider  # pragma: no cover
except ModuleNotFoundError:
    logger.exception('EtcHostsProvider has been moved into a seperate module, '
                     'octodns_etchosts is now required. Provider class should '
                     'be updated to octodns_etchosts.EtcHostsProvider. See '
                     'See https://github.com/octodns/octodns#updating-'
                     'to-use-extracted-providers for more information.')
    raise
