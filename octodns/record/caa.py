#
#
#

import re

from ..equality import EqualityTupleMixin
from .base import Record, ValuesMixin, unquote
from .rr import RrParseError
from .validator import ValueValidator


class CaaValueValidator(ValueValidator):
    '''
    Validates CAA rdata: ``flags`` is an integer in [0, 255], and
    ``tag`` and ``value`` are present.
    '''

    def validate(self, value_cls, data, _type):
        reasons = []
        for value in data:
            try:
                flags = int(value.get('flags', 0))
                if flags < 0 or flags > 255:
                    reasons.append(f'invalid flags "{flags}"')
            except ValueError:
                reasons.append(f'invalid flags "{value["flags"]}"')

            if 'tag' not in value:
                reasons.append('missing tag')
            if 'value' not in value:
                reasons.append('missing value')
        return reasons


class CaaValueRfcValidator(ValueValidator):
    '''
    Strict CAA rdata validator per RFC 8659 §4.1.

    - ``flags`` must be 0 or 128 — only bit 0 (Issuer Critical) is
      defined; all other bits are reserved and must be zero.
    - ``tag`` must match ``[a-zA-Z0-9]+``.

    Enabled as part of the ``strict`` validator set::

      manager:
        enabled:
          - strict
    '''

    _tag_re = re.compile(r'^[a-zA-Z0-9]+$')

    def validate(self, value_cls, data, _type):
        reasons = []
        for value in data:
            try:
                flags = int(value.get('flags', 0))
                if flags not in (0, 128):
                    reasons.append(
                        f'flags "{flags}" is not valid; must be 0 or 128'
                    )
            except (ValueError, TypeError):
                reasons.append(f'invalid flags "{value["flags"]}"')

            tag = value.get('tag')
            if not tag:
                reasons.append('missing tag')
            elif not self._tag_re.match(tag):
                reasons.append(f'invalid tag "{tag}"')

            if 'value' not in value:
                reasons.append('missing value')
        return reasons


class CaaValueBestPracticeValidator(ValueValidator):
    '''
    Checks that CAA records include an explicit ``issuewild`` property
    whenever an ``issue`` property is present.

    Per RFC 8659 §4.2, wildcard certificate issuance falls back to
    ``issue`` policy when no ``issuewild`` record exists; omitting
    ``issuewild`` makes the wildcard-issuance policy implicit rather
    than explicit.

    Enabled as part of the ``best-practice`` validator set::

      manager:
        enabled:
          - best-practice
    '''

    def validate(self, value_cls, data, _type):
        tags = {v.get('tag') for v in data}
        if 'issue' in tags and 'issuewild' not in tags:
            return [
                'CAA issue tag is present without issuewild; '
                'add an explicit issuewild to clarify wildcard certificate policy'
            ]
        return []


class CaaValue(EqualityTupleMixin, dict):
    # https://tools.ietf.org/html/rfc8659

    VALIDATORS = [
        CaaValueValidator('caa-value', sets={'legacy'}),
        CaaValueRfcValidator('caa-value-rfc', sets={'strict'}),
        CaaValueBestPracticeValidator(
            'caa-value-best-practice', sets={'best-practice'}
        ),
    ]

    @classmethod
    def _schema(cls):
        return {
            'type': 'object',
            'required': ['tag', 'value'],
            'properties': {
                'flags': {'type': 'integer', 'minimum': 0, 'maximum': 255},
                'tag': {'type': 'string'},
                'value': {'type': 'string'},
            },
        }

    @classmethod
    def parse_rdata_text(cls, value):
        try:
            # value may contain whitepsace
            flags, tag, value = value.split(' ', 2)
        except ValueError:
            raise RrParseError()
        try:
            flags = int(flags)
        except ValueError:
            pass
        tag = unquote(tag)
        value = unquote(value)
        return {'flags': flags, 'tag': tag, 'value': value}

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        super().__init__(
            {
                'flags': int(value.get('flags', 0)),
                'tag': value['tag'],
                'value': value['value'],
            }
        )

    @property
    def flags(self):
        return self['flags']

    @flags.setter
    def flags(self, value):
        self['flags'] = value

    @property
    def tag(self):
        return self['tag']

    @tag.setter
    def tag(self, value):
        self['tag'] = value

    @property
    def value(self):
        return self['value']

    @value.setter
    def value(self, value):
        self['value'] = value

    @property
    def data(self):
        return self

    @property
    def rdata_text(self):
        return f'{self.flags} {self.tag} {self.value}'

    def template(self, params):
        if '{' not in self.value:
            return self
        new = self.__class__(self)
        new.value = new.value.format(**params)
        return new

    def _equality_tuple(self):
        return (self.flags, self.tag, self.value)

    def __repr__(self):
        return f'{self.flags} {self.tag} "{self.value}"'


class CaaRecord(ValuesMixin, Record):
    REFERENCES = (
        'https://datatracker.ietf.org/doc/html/rfc8657',
        'https://datatracker.ietf.org/doc/html/rfc8659',
        'https://datatracker.ietf.org/doc/html/rfc9495',
    )
    _type = 'CAA'
    _value_type = CaaValue


Record.register_type(CaaRecord)
