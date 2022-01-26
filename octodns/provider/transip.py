#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger

logger = getLogger('Transip')
try:
    logger.warning('octodns_transip shimmed. Update your provider class to '
                   'octodns_transip.TransipProvider. '
                   'Shim will be removed in 1.0')
    from octodns_transip import TransipProvider
    TransipProvider  # pragma: no cover
except ModuleNotFoundError:
    logger.exception('TransipProvider has been moved into a seperate module, '
                     'octodns_transip is now required. Provider class should '
                     'be updated to octodns_transip.TransipProvider. See '
                     'https://github.com/octodns/octodns#updating-'
                     'to-use-extracted-providers for more information.')
    raise
