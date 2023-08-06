#
#
#

from ..idna import idna_decode


class RecordException(Exception):
    pass


class ValidationError(RecordException):
    @classmethod
    def build_message(cls, fqdn, reasons, context=None):
        reasons = '\n  - '.join(reasons)
        msg = f'Invalid record "{idna_decode(fqdn)}"'
        if context:
            msg += f', {context}'
        msg += f'\n  - {reasons}'
        return msg

    def __init__(self, fqdn, reasons, context=None):
        super().__init__(self.build_message(fqdn, reasons, context))
        self.fqdn = fqdn
        self.reasons = reasons
        self.context = context
