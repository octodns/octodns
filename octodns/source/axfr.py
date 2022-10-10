#
#
#

from logging import getLogger

logger = getLogger('AXFR')
try:
    logger.warning(
        'octodns_bind shimmed. Update your provider class to octodns_bind.AxfrSource or octodns_bind.ZoneFileSource. Shim will be removed in 1.0'
    )
    from octodns_bind import AxfrSource, ZoneFileSource

    AxfrSource  # pragma: no cover
    ZoneFileSource  # pragma: no cover
except ModuleNotFoundError:
    logger.exception(
        'AXFR/Zone file support has been moved into a separate module, octodns_bind is now required. Provider classes should be updated to octodns_bind.AxfrSource or octodns_bind.ZoneFileSource. See https://github.com/octodns/octodns#updating-to-use-extracted-providers for more information.'
    )
    raise
