#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger

logger = getLogger('Constellix')
try:
    logger.warning('octodns_constellix shimmed. Update your provider class to '
                   'octodns_constellix.ConstellixProvider. '
                   'Shim will be removed in 1.0')
    from octodns_constellix import ConstellixProvider
    ConstellixProvider  # pragma: no cover
except ModuleNotFoundError:
    logger.exception('ConstellixProvider has been moved into a seperate '
                     'module, octodns_constellix is now required. Provider '
                     'class should be updated to '
                     'octodns_constellix.ConstellixProvider. See '
                     'https://github.com/octodns/octodns#updating-'
                     'to-use-extracted-providers for more information.')
    raise
