#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger

logger = getLogger('Route53')
try:
    logger.warning('octodns_route53 shimmed. Update your provider class to '
                   'octodns_route53.Route53Provider. '
                   'Shim will be removed in 1.0')
    from octodns_route53 import Route53Provider
    Route53Provider  # pragma: no cover
except ModuleNotFoundError:
    logger.exception('Route53Provider has been moved into a seperate module, '
                     'octodns_route53 is now required. Provider class should '
                     'be updated to octodns_route53.Route53Provider. See '
                     'https://github.com/octodns/octodns#updating-'
                     'to-use-extracted-providers for more information.')
    raise
