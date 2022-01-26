#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger

logger = getLogger('GCore')
try:
    logger.warning('octodns_gcore shimmed. Update your provider class to '
                   'octodns_gcore.GCoreProvider. '
                   'Shim will be removed in 1.0')
    from octodns_gcore import GCoreProvider
    GCoreProvider  # pragma: no cover
except ModuleNotFoundError:
    logger.exception('GCoreProvider has been moved into a seperate module, '
                     'octodns_gcore is now required. Provider class should '
                     'be updated to octodns_gcore.GCoreProvider. See '
                     'https://github.com/octodns/octodns#updating-'
                     'to-use-extracted-providers for more information.')
    raise
