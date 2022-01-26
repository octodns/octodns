#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger

logger = getLogger('Gandi')
try:
    logger.warning('octodns_gandi shimmed. Update your provider class to '
                   'octodns_gandi.GandiProvider. '
                   'Shim will be removed in 1.0')
    from octodns_gandi import GandiProvider
    GandiProvider  # pragma: no cover
except ModuleNotFoundError:
    logger.exception('GandiProvider has been moved into a seperate module, '
                     'octodns_gandi is now required. Provider class should '
                     'be updated to octodns_gandi.GandiProvider. See '
                     'https://github.com/octodns/octodns#updating-'
                     'to-use-extracted-providers for more information.')
    raise
