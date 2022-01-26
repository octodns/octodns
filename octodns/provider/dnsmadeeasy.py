#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger

logger = getLogger('DnsMadeEasy')
try:
    logger.warning('octodns_dnsmadeeasy shimmed. Update your provider class '
                   'to octodns_dnsmadeeasy.DnsMadeEasyProvider. '
                   'Shim will be removed in 1.0')
    from octodns_dnsmadeeasy import DnsMadeEasyProvider
    DnsMadeEasyProvider  # pragma: no cover
except ModuleNotFoundError:
    logger.exception('DnsMadeEasyProvider has been moved into a seperate '
                     'module, octodns_dnsmadeeasy is now required. Provider '
                     'class should be updated to '
                     'octodns_dnsmadeeasy.DnsMadeEasyProvider. See '
                     'https://github.com/octodns/octodns#updating-'
                     'to-use-extracted-providers for more information.')
    raise
