#
#
#

from ..equality import EqualityTupleMixin
from .base import Record, ValuesMixin, unquote
from .rr import RrParseError
from .validator import ValueValidator


class TlsaValueValidator(ValueValidator):
    @classmethod
    def validate(cls, value_cls, data, _type):
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


class TlsaValue(EqualityTupleMixin, dict):
    VALIDATORS = [TlsaValueValidator]

    @classmethod
    def _schema(cls):
        return {
            'type': 'object',
            'required': [
                'certificate_usage',
                'selector',
                'matching_type',
                'certificate_association_data',
            ],
            'properties': {
                'certificate_usage': {
                    'type': 'integer',
                    'minimum': 0,
                    'maximum': 3,
                },
                'selector': {'type': 'integer', 'minimum': 0, 'maximum': 1},
                'matching_type': {
                    'type': 'integer',
                    'minimum': 0,
                    'maximum': 2,
                },
                'certificate_association_data': {'type': 'string'},
            },
        }

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
        for validator in TlsaValue.VALIDATORS:
            reasons.extend(validator.validate(cls, data, _type))
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

    def template(self, params):
        if '{' not in self.certificate_association_data:
            return self
        new = self.__class__(self)
        new.certificate_association_data = (
            new.certificate_association_data.format(**params)
        )
        return new

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
    REFERENCES = (
        'https://datatracker.ietf.org/doc/html/rfc6698',
        'https://datatracker.ietf.org/doc/html/rfc7671',
        'https://datatracker.ietf.org/doc/html/rfc7672',
        'https://datatracker.ietf.org/doc/html/rfc7673',
    )
    _type = 'TLSA'
    _value_type = TlsaValue


Record.register_type(TlsaRecord)
