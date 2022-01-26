#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger

logger = getLogger('MythicBeasts')
try:
    logger.warning('octodns_mythicbeasts shimmed. Update your provider class '
                   'to octodns_mythicbeasts.MythicBeastsProvider. '
                   'Shim will be removed in 1.0')
    from octodns_mythicbeasts import MythicBeastsProvider
    MythicBeastsProvider  # pragma: no cover
except ModuleNotFoundError:
    logger.exception('MythicBeastsProvider has been moved into a seperate '
                     'module, octodns_mythicbeasts is now required. Provider '
                     'class should be updated to '
                     'octodns_mythicbeasts.MythicBeastsProvider. See '
                     'https://github.com/octodns/octodns#updating-'
                     'to-use-extracted-providers for more information.')
    raise
