#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger

logger = getLogger('DigitalOcean')
try:
    logger.warning('octodns_digitalocean shimmed. Update your provider class '
                   'to octodns_digitalocean.DigitalOceanProvider. Shim will '
                   'be removed in 1.0')
    from octodns_digitalocean import DigitalOceanProvider
    DigitalOceanProvider  # pragma: no cover
except ModuleNotFoundError:
    logger.exception('DigitalOceanProvider has been moved into a seperate '
                     'module, octodns_digitalocean is now required. Provider '
                     'class should be updated to '
                     'octodns_digitalocean.DigitalOceanProvider. See '
                     'https://github.com/octodns/octodns#updating-'
                     'to-use-extracted-providers for more information.')
    raise
