#
#
#

from ..idna import idna_decode


class RecordException(Exception):
    pass


class ValidationError(RecordException):
    @classmethod
    def build_message(cls, fqdn, reasons):
        reasons = '\n  - '.join(reasons)
        return f'Invalid record "{idna_decode(fqdn)}"\n  - {reasons}'

    def __init__(self, fqdn, reasons):
        super().__init__(self.build_message(fqdn, reasons))
        self.fqdn = fqdn
        self.reasons = reasons
