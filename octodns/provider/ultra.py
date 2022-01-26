#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger

logger = getLogger('Ultra')
try:
    logger.warning('octodns_ultra shimmed. Update your provider class to '
                   'octodns_ultra.UltraProvider. '
                   'Shim will be removed in 1.0')
    from octodns_ultra import UltraProvider
    UltraProvider  # pragma: no cover
except ModuleNotFoundError:
    logger.exception('UltraProvider has been moved into a seperate module, '
                     'octodns_ultra is now required. Provider class should '
                     'be updated to octodns_ultra.UltraProvider. See '
                     'https://github.com/octodns/octodns#updating-'
                     'to-use-extracted-providers for more information.')
    raise
