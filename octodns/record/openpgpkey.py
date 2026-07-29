#
#
#

from ..deprecation import deprecated
from .base import Record, ValuesMixin
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
    def from_rrs(cls, rdata):
        # Strip whitespace that may appear in zone files (base64 data may be
        # split across lines)
        return rdata.replace(' ', '')

    @classmethod
    def parse_rdata_text(cls, value):
        deprecated(
            f'`{cls.__name__}.parse_rdata_text` is DEPRECATED. Use `{cls.__name__}.from_rrs()` instead. Will be removed in 2.0',
            stacklevel=2,
        )
        return cls.from_rrs(value)

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def to_rrs(self):
        return self

    @property
    def rdata_text(self):
        deprecated(
            f'`{self.__class__.__name__}.rdata_text` is DEPRECATED. Use `{self.__class__.__name__}.to_rrs()` instead. Will be removed in 2.0',
            stacklevel=2,
        )
        return self.to_rrs()

    def template(self, params):
        if '{' not in self:
            return self
        return self.__class__(self.format(**params))


class OpenpgpkeyRecord(ValuesMixin, Record):
    REFERENCES = ('https://datatracker.ietf.org/doc/html/rfc7929',)
    _type = 'OPENPGPKEY'
    _value_type = OpenpgpkeyValue


Record.register_type(OpenpgpkeyRecord)
