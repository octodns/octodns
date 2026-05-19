#
#
#

from typing import Iterable, Optional

from ..idna import idna_decode


class ZoneException(Exception):
    pass


class ValidationError(ZoneException):
    @classmethod
    def build_message(
        cls,
        zone_name: str,
        reasons: Iterable[str],
        context: Optional[str] = None,
    ) -> str:
        reasons_str = '\n  - '.join([str(r) for r in reasons])
        msg = f'Invalid zone "{idna_decode(zone_name)}"'
        if context:
            msg += f', {context}'
        msg += f'\n  - {reasons_str}'
        return msg

    def __init__(
        self,
        zone_name: str,
        reasons: Iterable[str],
        context: Optional[str] = None,
    ) -> None:
        super().__init__(self.build_message(zone_name, reasons, context))
        self.zone_name = zone_name
        self.reasons = list(reasons)
        self.context = context
