#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger

logger = getLogger('Hetzner')
try:
    logger.warning('octodns_hetzner shimmed. Update your provider class to '
                   'octodns_hetzner.HetznerProvider. '
                   'Shim will be removed in 1.0')
    from octodns_hetzner import HetznerProvider
    HetznerProvider  # pragma: no cover
except ModuleNotFoundError:
    logger.exception('HetznerProvider has been moved into a seperate module, '
                     'octodns_hetzner is now required. Provider class should '
                     'be updated to octodns_hetzner.HetznerProvider. See '
                     'https://github.com/octodns/octodns#updating-'
                     'to-use-extracted-providers for more information.')
    raise
