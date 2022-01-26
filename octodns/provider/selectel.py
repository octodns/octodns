#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger

logger = getLogger('Selectel')
try:
    logger.warning('octodns_selectel shimmed. Update your provider class to '
                   'octodns_selectel.SelectelProvider. '
                   'Shim will be removed in 1.0')
    from octodns_selectel import SelectelProvider
    SelectelProvider  # pragma: no cover
except ModuleNotFoundError:
    logger.exception('SelectelProvider has been moved into a seperate module, '
                     'octodns_selectel is now required. Provider class should '
                     'be updated to octodns_selectel.SelectelProvider. See '
                     'https://github.com/octodns/octodns#updating-'
                     'to-use-extracted-providers for more information.')
    raise
