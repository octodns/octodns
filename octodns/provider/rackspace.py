#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger

logger = getLogger('Rackspace')
try:
    logger.warning('octodns_rackspace shimmed. Update your provider class to '
                   'octodns_rackspace.RackspaceProvider. '
                   'Shim will be removed in 1.0')
    from octodns_rackspace import RackspaceProvider
    RackspaceProvider  # pragma: no cover
except ModuleNotFoundError:
    logger.exception('RackspaceProvider has been moved into a seperate '
                     'module, octodns_rackspace is now required. Provider '
                     'class should be updated to '
                     'octodns_rackspace.RackspaceProvider. See '
                     'https://github.com/octodns/octodns#updating-'
                     'to-use-extracted-providers for more information.')
    raise
