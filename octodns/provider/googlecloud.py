#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger

logger = getLogger('GoogleCloud')
try:
    logger.warning('octodns_googlecloud shimmed. Update your provider class '
                   'to octodns_googlecloud.GoogleCloudProvider. '
                   'Shim will be removed in 1.0')
    from octodns_googlecloud import GoogleCloudProvider
    GoogleCloudProvider  # pragma: no cover
except ModuleNotFoundError:
    logger.exception('GoogleCloudProvider has been moved into a seperate '
                     'module, octodns_googlecloud is now required. Provider '
                     'class should be updated to '
                     'octodns_googlecloud.GoogleCloudProvider. See '
                     'https://github.com/octodns/octodns#updating-'
                     'to-use-extracted-providers for more information.')
    raise
