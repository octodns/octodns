#
#
#

import re

from ..equality import EqualityTupleMixin
from .base import Record, ValuesMixin, unquote
from .rr import RrParseError
from .validator import ValueValidator


class TlsaValueValidator(ValueValidator):
    '''
    Validates TLSA rdata: ``certificate_usage`` in [0, 3],
    ``selector`` in [0, 1], ``matching_type`` in [0, 2], and
    ``certificate_association_data`` is present.
    '''

    def validate(self, value_cls, data, _type):
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


class TlsaValueRfcValidator(ValueValidator):
    '''
    Strict TLSA rdata validator per RFC 6698.

    - ``certificate_usage``, ``selector``, and ``matching_type`` must each be
      integers in [0, 255] (uint8 fields).
    - ``certificate_association_data`` must be a valid hexadecimal string.
    - When ``matching_type`` is 1 (SHA-256), the data must be exactly 64 hex
      characters (32 bytes).
    - When ``matching_type`` is 2 (SHA-512), the data must be exactly 128 hex
      characters (64 bytes).

    Enabled as part of the ``strict`` validator set::

      manager:
        enabled:
          - strict
    '''

    _hex_re = re.compile(r'^[0-9a-fA-F]+$')
    _matching_type_lengths = {1: 64, 2: 128}

    def validate(self, value_cls, data, _type):
        reasons = []
        for value in data:
            matching_type = None
            for field in ('certificate_usage', 'selector', 'matching_type'):
                if field not in value:
                    reasons.append(f'missing {field}')
                else:
                    try:
                        int_val = int(value[field])
                        if not 0 <= int_val <= 255:
                            reasons.append(
                                f'invalid {field} "{int_val}"; must be 0-255'
                            )
                        elif field == 'matching_type':
                            matching_type = int_val
                    except (ValueError, TypeError):
                        reasons.append(f'invalid {field} "{value[field]}"')

            if 'certificate_association_data' not in value:
                reasons.append('missing certificate_association_data')
            else:
                cad = value['certificate_association_data']
                if not cad or not self._hex_re.match(str(cad)):
                    reasons.append(
                        f'invalid certificate_association_data "{cad}"; must be hex'
                    )
                elif matching_type in self._matching_type_lengths:
                    expected = self._matching_type_lengths[matching_type]
                    if len(str(cad)) != expected:
                        reasons.append(
                            f'certificate_association_data must be {expected} hex characters for matching_type {matching_type}'
                        )
        return reasons


class TlsaValueBestPracticeValidator(ValueValidator):
    '''
    Checks that TLSA records do not use matching_type 0 (full
    DER-encoded certificate or public key stored verbatim).

    RFC 7671 §4.1 advises against matching_type 0 in production:
    any certificate renewal requires a DNS update before the new
    certificate can be used.  Use matching_type 1 (SHA-256) or
    2 (SHA-512) instead.

    Enabled as part of the ``best-practice`` validator set::

      manager:
        enabled:
          - best-practice
    '''

    def validate(self, value_cls, data, _type):
        reasons = []
        for value in data:
            try:
                matching_type = int(value['matching_type'])
            except (KeyError, ValueError, TypeError):
                continue
            if matching_type == 0:
                reasons.append(
                    'TLSA matching_type 0 (full data) is not recommended; '
                    'use matching_type 1 (SHA-256) or 2 (SHA-512)'
                )
        return reasons


class TlsaValue(EqualityTupleMixin, dict):
    VALIDATORS = [
        TlsaValueValidator('tlsa-value', sets={'legacy'}),
        TlsaValueRfcValidator('tlsa-value-rfc', sets={'strict'}),
        TlsaValueBestPracticeValidator(
            'tlsa-value-best-practice', sets={'best-practice'}
        ),
    ]

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
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        super().__init__(
            {
                'certificate_usage': int(value.get('certificate_usage', 0)),
                'selector': int(value.get('selector', 0)),
                'matching_type': int(value.get('matching_type', 0)),
                # force to str (hex-only values may be coerced to int) and
                # normalize to lowercase for case-insensitive comparison
                'certificate_association_data': str(
                    value['certificate_association_data']
                ).lower(),
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
        return f"'{self.certificate_usage} {self.selector} {self.matching_type} {self.certificate_association_data}'"


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
