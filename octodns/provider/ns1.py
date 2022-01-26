#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger

logger = getLogger('Ns1')
try:
    logger.warning('octodns_ns1 shimmed. Update your provider class to '
                   'octodns_ns1.Ns1Provider. '
                   'Shim will be removed in 1.0')
    from octodns_ns1 import Ns1Provider
    Ns1Provider  # pragma: no cover
except ModuleNotFoundError:
    logger.exception('Ns1Provider has been moved into a seperate module, '
                     'octodns_ns1 is now required. Provider class should '
                     'be updated to octodns_ns1.Ns1Provider. See '
                     'https://github.com/octodns/octodns#updating-'
                     'to-use-extracted-providers for more information.')
    raise
