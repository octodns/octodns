#
#
#

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


from ..idna import idna_decode


class RecordException(Exception):
    pass


class ValidationError(RecordException):
    @classmethod
    def build_message(
        cls, fqdn: str, reasons: Iterable[str], context: str | None = None
    ) -> str:
        reasons_str = '\n  - '.join(reasons)
        msg = f'Invalid record "{idna_decode(fqdn)}"'
        if context:
            msg += f', {context}'
        msg += f'\n  - {reasons_str}'
        return msg

    def __init__(
        self, fqdn: str, reasons: Iterable[str], context: str | None = None
    ) -> None:
        super().__init__(self.build_message(fqdn, reasons, context))
        self.fqdn = fqdn
        self.reasons = reasons
        self.context = context
