#
#
#

from typing import Iterable, Optional

from ..idna import idna_decode


class RecordException(Exception):
    pass


class ValidationError(RecordException):
    @classmethod
    def build_message(
        cls, fqdn: str, reasons: Iterable[str], context: Optional[str] = None
    ) -> str:
        reasons_str = '\n  - '.join(reasons)
        msg = f'Invalid record "{idna_decode(fqdn)}"'
        if context:
            msg += f', {context}'
        msg += f'\n  - {reasons_str}'
        return msg

    def __init__(
        self, fqdn: str, reasons: Iterable[str], context: Optional[str] = None
    ) -> None:
        super().__init__(self.build_message(fqdn, reasons, context))
        self.fqdn = fqdn
        self.reasons = list(reasons)
        self.context = context
