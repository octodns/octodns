#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger

logger = getLogger('Azure')
try:
    logger.warning('octodns_azure shimmed. Update your provider class to '
                   'octodns_azure.AzureProvider. '
                   'Shim will be removed in 1.0')
    from octodns_azure import AzureProvider
    AzureProvider  # pragma: no cover
except ModuleNotFoundError:
    logger.exception('AzureProvider has been moved into a seperate module, '
                     'octodns_azure is now required. Provider class should '
                     'be updated to octodns_azure.AzureProvider. See '
                     'https://github.com/octodns/octodns#updating-'
                     'to-use-extracted-providers for more information.')
    raise
