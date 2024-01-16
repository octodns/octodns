#
#
#

from fqdn import FQDN

from ..equality import EqualityTupleMixin
from ..idna import idna_encode
from .base import Record, ValuesMixin, unquote
from .rr import RrParseError


class MxValue(EqualityTupleMixin, dict):
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
    def validate(cls, data, _type):
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
                exchange = value.get('exchange', None) or value['value']
                if not exchange:
                    reasons.append('missing exchange')
                    continue
                exchange = idna_encode(exchange)
                if (
                    exchange != '.'
                    and not FQDN(exchange, allow_underscores=True).is_valid
                ):
                    reasons.append(
                        f'Invalid MX exchange "{exchange}" is not '
                        'a valid FQDN.'
                    )
                elif not exchange.endswith('.'):
                    reasons.append(f'MX value "{exchange}" missing trailing .')
            except KeyError:
                reasons.append('missing exchange')
        return reasons

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

    def __hash__(self):
        return hash((self.preference, self.exchange))

    def _equality_tuple(self):
        return (self.preference, self.exchange)

    def __repr__(self):
        return f"'{self.preference} {self.exchange}'"


class MxRecord(ValuesMixin, Record):
    _type = 'MX'
    _value_type = MxValue


Record.register_type(MxRecord)
