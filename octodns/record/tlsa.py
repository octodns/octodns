#
#
#

from ..equality import EqualityTupleMixin
from .base import Record, ValuesMixin, unquote
from .rr import RrParseError


class TlsaValue(EqualityTupleMixin, dict):
    @classmethod
    def parse_rdata_text(self, value):
        try:
            (
                certificate_usage,
                selector,
                matching_type,
                certificate_association_data,
            ) = value.split(' ')
        except ValueError:
            raise RrParseError()
        try:
            certificate_usage = int(certificate_usage)
        except ValueError:
            pass
        try:
            selector = int(selector)
        except ValueError:
            pass
        try:
            matching_type = int(matching_type)
        except ValueError:
            pass
        certificate_association_data = unquote(certificate_association_data)
        return {
            'certificate_usage': certificate_usage,
            'selector': selector,
            'matching_type': matching_type,
            'certificate_association_data': certificate_association_data,
        }

    @classmethod
    def validate(cls, data, _type):
        reasons = []
        for value in data:
            try:
                certificate_usage = int(value.get('certificate_usage', 0))
                if certificate_usage < 0 or certificate_usage > 3:
                    reasons.append(
                        f'invalid certificate_usage ' f'"{certificate_usage}"'
                    )
            except ValueError:
                reasons.append(
                    f'invalid certificate_usage '
                    f'"{value["certificate_usage"]}"'
                )

            try:
                selector = int(value.get('selector', 0))
                if selector < 0 or selector > 1:
                    reasons.append(f'invalid selector "{selector}"')
            except ValueError:
                reasons.append(f'invalid selector "{value["selector"]}"')

            try:
                matching_type = int(value.get('matching_type', 0))
                if matching_type < 0 or matching_type > 2:
                    reasons.append(f'invalid matching_type "{matching_type}"')
            except ValueError:
                reasons.append(
                    f'invalid matching_type ' f'"{value["matching_type"]}"'
                )

            if 'certificate_usage' not in value:
                reasons.append('missing certificate_usage')
            if 'selector' not in value:
                reasons.append('missing selector')
            if 'matching_type' not in value:
                reasons.append('missing matching_type')
            if 'certificate_association_data' not in value:
                reasons.append('missing certificate_association_data')
        return reasons

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        super().__init__(
            {
                'certificate_usage': int(value.get('certificate_usage', 0)),
                'selector': int(value.get('selector', 0)),
                'matching_type': int(value.get('matching_type', 0)),
                # force it to a string, in case the hex has only numerical
                # values and it was converted to an int at some point
                # TODO: this needed on any others?
                'certificate_association_data': str(
                    value['certificate_association_data']
                ),
            }
        )

    @property
    def certificate_usage(self):
        return self['certificate_usage']

    @certificate_usage.setter
    def certificate_usage(self, value):
        self['certificate_usage'] = value

    @property
    def selector(self):
        return self['selector']

    @selector.setter
    def selector(self, value):
        self['selector'] = value

    @property
    def matching_type(self):
        return self['matching_type']

    @matching_type.setter
    def matching_type(self, value):
        self['matching_type'] = value

    @property
    def certificate_association_data(self):
        return self['certificate_association_data']

    @certificate_association_data.setter
    def certificate_association_data(self, value):
        self['certificate_association_data'] = value

    @property
    def rdata_text(self):
        return f'{self.certificate_usage} {self.selector} {self.matching_type} {self.certificate_association_data}'

    def _equality_tuple(self):
        return (
            self.certificate_usage,
            self.selector,
            self.matching_type,
            self.certificate_association_data,
        )

    def __repr__(self):
        return (
            f"'{self.certificate_usage} {self.selector} '"
            f"'{self.matching_type} {self.certificate_association_data}'"
        )


class TlsaRecord(ValuesMixin, Record):
    _type = 'TLSA'
    _value_type = TlsaValue


Record.register_type(TlsaRecord)
