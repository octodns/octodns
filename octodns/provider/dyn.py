#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger

logger = getLogger('Dyn')
try:
    logger.warning('octodns_dyn shimmed. Update your provider class to '
                   'octodns_dyn.DynProvider. '
                   'Shim will be removed in 1.0')
    from octodns_dyn import DynProvider
    DynProvider  # pragma: no cover
except ModuleNotFoundError:
    logger.exception('DynProvider has been moved into a seperate module, '
                     'octodns_dyn is now required. Provider class should '
                     'be updated to octodns_dyn.DynProvider. See '
                     'https://github.com/octodns/octodns#updating-'
                     'to-use-extracted-providers for more information.')
    raise
