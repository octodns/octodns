#
#
#

from ..equality import EqualityTupleMixin
from .base import Record, ValuesMixin, unquote
from .rr import RrParseError
from .target import _check_target_trailing_dot
from .validator import ValueValidator


class NaptrValueValidator(ValueValidator):
    '''
    Validates NAPTR rdata: ``order`` and ``preference`` are
    integer-parsable, ``flags`` is one of the RFC 3403 values, and
    ``service``, ``regexp``, and ``replacement`` are all present.
    '''

    def validate(self, value_cls, data, _type):
        reasons = []
        for value in data:
            try:
                int(value['order'])
            except KeyError:
                reasons.append('missing order')
            except ValueError:
                reasons.append(f'invalid order "{value["order"]}"')
            try:
                int(value['preference'])
            except KeyError:
                reasons.append('missing preference')
            except ValueError:
                reasons.append(f'invalid preference "{value["preference"]}"')
            try:
                flags = value['flags']
                if flags not in value_cls.VALID_FLAGS:
                    reasons.append(f'unrecognized flags "{flags}"')
            except KeyError:
                reasons.append('missing flags')

            # TODO: validate these... they're non-trivial
            for k in ('service', 'regexp', 'replacement'):
                if k not in value:
                    reasons.append(f'missing {k}')

        return reasons


class NaptrValueRfcValidator(ValueValidator):
    '''
    Strict NAPTR rdata validator per RFC 3403 §4.1.

    - ``order`` and ``preference`` must be integers in [0, 65535] (uint16).
    - ``flags`` must be one of ``S``, ``A``, ``U``, ``P`` (case-insensitive)
      or empty.
    - ``replacement`` must be a fully-qualified domain name (ending with
      ``"."``) or ``"."`` for the null replacement.

    Enabled as part of the ``strict`` validator set::

      manager:
        enabled:
          - strict
    '''

    _valid_flags = frozenset('SAUP')

    def validate(self, value_cls, data, _type):
        reasons = []
        for value in data:
            for field in ('order', 'preference'):
                if field not in value:
                    reasons.append(f'missing {field}')
                else:
                    try:
                        int_val = int(value[field])
                        if not 0 <= int_val <= 65535:
                            reasons.append(
                                f'invalid {field} "{int_val}"; must be 0-65535'
                            )
                    except (ValueError, TypeError):
                        reasons.append(f'invalid {field} "{value[field]}"')

            if 'flags' not in value:
                reasons.append('missing flags')
            else:
                flags = value['flags']
                if flags and flags.upper() not in self._valid_flags:
                    reasons.append(f'unrecognized flags "{flags}"')

            for k in ('service', 'regexp'):
                if k not in value:
                    reasons.append(f'missing {k}')

            if 'replacement' not in value:
                reasons.append('missing replacement')

        return reasons


class NaptrValueBestPracticeValidator(ValueValidator):
    '''
    Checks that the NAPTR ``replacement`` field ends with a trailing
    ``.`` (fully-qualified name) when non-empty and not the null
    replacement ``"."``.

    Enabled as part of the ``best-practice`` validator set::

      manager:
        enabled:
          - best-practice
    '''

    def validate(self, value_cls, data, _type):
        reasons = []
        for value in data:
            replacement = value.get('replacement')
            if replacement:
                reasons += _check_target_trailing_dot(
                    replacement, _type, 'replacement'
                )
        return reasons


class NaptrValue(EqualityTupleMixin, dict):
    VALID_FLAGS = ('S', 'A', 'U', 'P', 's', 'a', 'u', 'p')

    VALIDATORS = [
        NaptrValueValidator('naptr-value', sets={'legacy'}),
        NaptrValueRfcValidator('naptr-value-rfc', sets={'strict'}),
        NaptrValueBestPracticeValidator(
            'naptr-value-best-practice', sets={'best-practice'}
        ),
    ]

    @classmethod
    def _schema(cls):
        return {
            'type': 'object',
            'required': [
                'order',
                'preference',
                'flags',
                'service',
                'regexp',
                'replacement',
            ],
            'properties': {
                'order': {'type': 'integer', 'minimum': 0, 'maximum': 65535},
                'preference': {
                    'type': 'integer',
                    'minimum': 0,
                    'maximum': 65535,
                },
                'flags': {'enum': list(cls.VALID_FLAGS)},
                'service': {'type': 'string'},
                'regexp': {'type': 'string'},
                'replacement': {'type': 'string'},
            },
        }

    @classmethod
    def parse_rdata_text(cls, value):
        try:
            order, preference, flags, service, regexp, replacement = (
                value.split(' ')
            )
        except ValueError:
            raise RrParseError()
        try:
            order = int(order)
            preference = int(preference)
        except ValueError:
            pass
        flags = unquote(flags)
        service = unquote(service)
        regexp = unquote(regexp)
        replacement = unquote(replacement)
        return {
            'order': order,
            'preference': preference,
            'flags': flags,
            'service': service,
            'regexp': regexp,
            'replacement': replacement,
        }

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        super().__init__(
            {
                'order': int(value['order']),
                'preference': int(value['preference']),
                'flags': value['flags'].upper(),
                'service': value['service'],
                'regexp': value['regexp'],
                'replacement': value['replacement'],
            }
        )

    @property
    def order(self):
        return self['order']

    @order.setter
    def order(self, value):
        self['order'] = value

    @property
    def preference(self):
        return self['preference']

    @preference.setter
    def preference(self, value):
        self['preference'] = value

    @property
    def flags(self):
        return self['flags']

    @flags.setter
    def flags(self, value):
        self['flags'] = value

    @property
    def service(self):
        return self['service']

    @service.setter
    def service(self, value):
        self['service'] = value

    @property
    def regexp(self):
        return self['regexp']

    @regexp.setter
    def regexp(self, value):
        self['regexp'] = value

    @property
    def replacement(self):
        return self['replacement']

    @replacement.setter
    def replacement(self, value):
        self['replacement'] = value

    @property
    def data(self):
        return self

    @property
    def rdata_text(self):
        # RFC 3403 requires flags, service, and regexp to be quoted character-strings
        flags = self.flags or ''
        service = self.service or ''
        regexp = self.regexp or ''
        return f'{self.order} {self.preference} "{flags}" "{service}" "{regexp}" {self.replacement}'

    def template(self, params):
        if (
            '{' not in self.service
            and '{' not in self.regexp
            and '{' not in self.replacement
        ):
            return self
        new = self.__class__(self)
        new.service = new.service.format(**params)
        new.regexp = new.regexp.format(**params)
        new.replacement = new.replacement.format(**params)
        return new

    def __hash__(self):
        return hash(self.__repr__())

    def _equality_tuple(self):
        return (
            self.order,
            self.preference,
            self.flags,
            self.service,
            self.regexp,
            self.replacement,
        )

    def __repr__(self):
        flags = self.flags if self.flags is not None else ''
        service = self.service if self.service is not None else ''
        regexp = self.regexp if self.regexp is not None else ''
        return (
            f"'{self.order} {self.preference} \"{flags}\" \"{service}\" "
            f"\"{regexp}\" {self.replacement}'"
        )


class NaptrRecord(ValuesMixin, Record):
    REFERENCES = (
        'https://datatracker.ietf.org/doc/html/rfc3401',
        'https://datatracker.ietf.org/doc/html/rfc3402',
        'https://datatracker.ietf.org/doc/html/rfc3403',
        'https://datatracker.ietf.org/doc/html/rfc3404',
        'https://datatracker.ietf.org/doc/html/rfc3405',
    )
    _type = 'NAPTR'
    _value_type = NaptrValue


Record.register_type(NaptrRecord)
