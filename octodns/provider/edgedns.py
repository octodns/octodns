#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger

logger = getLogger('Akamai')
try:
    logger.warning('octodns_edgedns shimmed. Update your provider class to '
                   'octodns_edgedns.AkamaiProvider. '
                   'Shim will be removed in 1.0')
    from octodns_edgedns import AkamaiProvider
    AkamaiProvider  # pragma: no cover
except ModuleNotFoundError:
    logger.exception('AkamaiProvider has been moved into a seperate module, '
                     'octodns_edgedns is now required. Provider class should '
                     'be updated to octodns_edgedns.AkamaiProvider. See '
                     'https://github.com/octodns/octodns#updating-'
                     'to-use-extracted-providers for more information.')
    raise
