#
#
#

from ..idna import idna_decode


class ZoneException(Exception):
    pass


class ValidationError(ZoneException):
    @classmethod
    def build_message(cls, zone_name, reasons, context=None):
        reasons = '\n  - '.join([str(r) for r in reasons])
        msg = f'Invalid zone "{idna_decode(zone_name)}"'
        if context:
            msg += f', {context}'
        msg += f'\n  - {reasons}'
        return msg

    def __init__(self, zone_name, reasons, context=None):
        super().__init__(self.build_message(zone_name, reasons, context))
        self.zone_name = zone_name
        self.reasons = reasons
        self.context = context
