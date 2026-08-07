#
#
#

from .base import (
    Record,
    ValuesMixin,
    _deprecated_parse_rdata_text,
    _deprecated_rdata_text,
)
from .validator import ValidationReason, ValueValidator


class OpenpgpkeyValueValidator(ValueValidator):
    '''
    Validates OPENPGPKEY values: at least one non-empty base64-encoded
    OpenPGP key must be provided.
    '''

    def validate(self, value_cls, data, _type):
        if not data or all(not d for d in data):
            return [ValidationReason('missing value(s)', validator_id=self.id)]
        return []


class OpenpgpkeyValue(str):
    '''
    OPENPGPKEY value - base64-encoded OpenPGP public key

    RFC 7929 - DANE Bindings for OpenPGP
    '''

    VALIDATORS = [
        OpenpgpkeyValueValidator(
            'openpgpkey-value-rfc', sets={'legacy', 'strict'}
        )
    ]

    @classmethod
    def _schema(cls):
        return {'type': 'string'}

    @classmethod
    def from_rdata_text(cls, value):
        '''Parse OPENPGPKEY RDATA presentation text into internal text.

        :param str value: OPENPGPKEY RDATA in master-file presentation format
        :returns: whitespace-normalized octoDNS internal-format text
        :rtype: str
        '''
        # Strip whitespace that may appear in zone files (base64 data may be
        # split across lines)
        return value.replace(' ', '')

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    @classmethod
    def parse_rdata_text(cls, value):
        _deprecated_parse_rdata_text(cls)
        return cls.from_rdata_text(value)

    @property
    def rdata_text(self):
        _deprecated_rdata_text(self)
        return self.to_rdata_text()

    def to_rdata_text(self):
        '''Render this internal OPENPGPKEY value as RDATA presentation text.

        :returns: OPENPGPKEY RDATA in master-file presentation format
        :rtype: str
        '''
        return self

    def template(self, params):
        if '{' not in self:
            return self
        return self.__class__(self.format(**params))


class OpenpgpkeyRecord(ValuesMixin, Record):
    REFERENCES = ('https://datatracker.ietf.org/doc/html/rfc7929',)
    _type = 'OPENPGPKEY'
    _value_type = OpenpgpkeyValue


Record.register_type(OpenpgpkeyRecord)
