#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger

logger = getLogger('Ovh')
try:
    logger.warning('octodns_ovh shimmed. Update your provider class to '
                   'octodns_ovh.OvhProvider. '
                   'Shim will be removed in 1.0')
    from octodns_ovh import OvhProvider
    OvhProvider  # pragma: no cover
except ModuleNotFoundError:
    logger.exception('OvhProvider has been moved into a seperate module, '
                     'octodns_ovh is now required. Provider class should '
                     'be updated to octodns_ovh.OvhProvider. See '
                     'https://github.com/octodns/octodns#updating-'
                     'to-use-extracted-providers for more information.')
    raise
