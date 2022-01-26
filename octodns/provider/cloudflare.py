#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger

logger = getLogger('Cloudflare')
try:
    logger.warning('octodns_cloudflare shimmed. Update your provider class to '
                   'octodns_cloudflare.CloudflareProvider. '
                   'Shim will be removed in 1.0')
    from octodns_cloudflare import CloudflareProvider
    CloudflareProvider  # pragma: no cover
except ModuleNotFoundError:
    logger.exception('CloudflareProvider has been moved into a seperate '
                     'module, octodns_cloudflare is now required. Provider '
                     'class should be updated to '
                     'octodns_cloudflare.CloudflareProvider. See '
                     'https://github.com/octodns/octodns#updating-'
                     'to-use-extracted-providers for more information.')
    raise
