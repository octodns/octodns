#
#
#

from .base import Record, ValuesMixin
from .validator import ValueValidator


class OpenpgpkeyValueValidator(ValueValidator):
    '''
    Validates OPENPGPKEY values: at least one non-empty base64-encoded
    OpenPGP key must be provided.
    '''

    def validate(self, value_cls, data, _type):
        if not data or all(not d for d in data):
            return ['missing value(s)']
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
    def parse_rdata_text(cls, value):
        # Strip whitespace that may appear in zone files (base64 data may be
        # split across lines)
        return value.replace(' ', '')

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    @property
    def rdata_text(self):
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
