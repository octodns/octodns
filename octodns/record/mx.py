#
#
#

from ..equality import EqualityTupleMixin
from ..idna import idna_encode
from .base import Record, ValuesMixin, unquote
from .rr import RrParseError
from .target import validate_target_fqdn
from .validator import ValueValidator


class MxValueValidator(ValueValidator):
    '''
    Validates MX rdata: an integer-parsable ``preference`` (or legacy
    ``priority`` alias) and a valid ``exchange`` FQDN (or legacy
    ``value`` alias).
    '''

    def validate(self, value_cls, data, _type):
        reasons = []
        for value in data:
            try:
                try:
                    int(value['preference'])
                except KeyError:
                    int(value['priority'])
            except KeyError:
                reasons.append('missing preference')
            except ValueError:
                reasons.append(f'invalid preference "{value["preference"]}"')
            exchange = None
            try:
                exchange = value.get('exchange') or value['value']
                reasons += validate_target_fqdn(exchange, _type, 'exchange')
            except KeyError:
                reasons.append('missing exchange')
        return reasons


class MxValueRfcValidator(ValueValidator):
    '''
    Strict MX rdata validator per RFC 5321 and RFC 7505.

    - ``preference`` must be in [0, 65535].
    - When ``exchange`` is ``"."``, ``preference`` must be 0 (null MX
      per RFC 7505 §3).
    - When ``exchange`` is not ``"."``, it must be a valid FQDN.

    Enabled as part of the ``strict`` validator set::

      manager:
        enabled:
          - strict
    '''

    def validate(self, value_cls, data, _type):
        reasons = []
        for value in data:
            preference = None
            if 'preference' in value or 'priority' in value:
                raw = value.get('preference', value.get('priority'))
                try:
                    preference = int(raw)
                    if not 0 <= preference <= 65535:
                        reasons.append(
                            f'preference "{preference}" out of range 0-65535'
                        )
                except (ValueError, TypeError):
                    reasons.append(f'invalid preference "{raw}"')
            else:
                reasons.append('missing preference')

            exchange = value.get('exchange') or value.get('value')
            if not exchange:
                reasons.append('missing exchange')
            elif exchange == '.':
                if preference is not None and preference != 0:
                    reasons.append(
                        'preference must be 0 for null MX (exchange ".")'
                    )
            else:
                reasons += validate_target_fqdn(exchange, _type, 'exchange')
        return reasons


class MxValue(EqualityTupleMixin, dict):
    VALIDATORS = [
        MxValueValidator('mx-value', sets={'legacy'}),
        MxValueRfcValidator('mx-value-rfc', sets={'strict'}),
    ]

    @classmethod
    def _schema(cls):
        return {
            'type': 'object',
            'properties': {
                'preference': {
                    'type': 'integer',
                    'minimum': 0,
                    'maximum': 65535,
                },
                # legacy alias for preference
                'priority': {'type': 'integer', 'minimum': 0, 'maximum': 65535},
                'exchange': {'type': 'string'},
                # legacy alias for exchange
                'value': {'type': 'string'},
            },
            'allOf': [
                {
                    'anyOf': [
                        {'required': ['preference']},
                        {'required': ['priority']},
                    ]
                },
                {
                    'anyOf': [
                        {'required': ['exchange']},
                        {'required': ['value']},
                    ]
                },
            ],
        }

    @classmethod
    def parse_rdata_text(cls, value):
        try:
            preference, exchange = value.split(' ')
        except ValueError:
            raise RrParseError()
        try:
            preference = int(preference)
        except ValueError:
            pass
        exchange = unquote(exchange)
        return {'preference': preference, 'exchange': exchange}

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        # RFC1035 says preference, half the providers use priority
        try:
            preference = value['preference']
        except KeyError:
            preference = value['priority']
        # UNTIL 1.0 remove value fallback
        try:
            exchange = value['exchange']
        except KeyError:
            exchange = value['value']
        super().__init__(
            {'preference': int(preference), 'exchange': idna_encode(exchange)}
        )

    @property
    def preference(self):
        return self['preference']

    @preference.setter
    def preference(self, value):
        self['preference'] = value

    @property
    def exchange(self):
        return self['exchange']

    @exchange.setter
    def exchange(self, value):
        self['exchange'] = value

    @property
    def data(self):
        return self

    @property
    def rdata_text(self):
        return f'{self.preference} {self.exchange}'

    def template(self, params):
        if '{' not in self.exchange:
            return self
        new = self.__class__(self)
        new.exchange = new.exchange.format(**params)
        return new

    def __hash__(self):
        return hash((self.preference, self.exchange))

    def _equality_tuple(self):
        return (self.preference, self.exchange)

    def __repr__(self):
        return f"'{self.preference} {self.exchange}'"


class MxRecord(ValuesMixin, Record):
    REFERENCES = (
        'https://datatracker.ietf.org/doc/html/rfc1035',
        'https://datatracker.ietf.org/doc/html/rfc5321',
        'https://datatracker.ietf.org/doc/html/rfc7505',
    )
    _type = 'MX'
    _value_type = MxValue


Record.register_type(MxRecord)
