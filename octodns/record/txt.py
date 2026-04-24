#
#
#

from .base import Record
from .chunked import ChunkedValueValidator, _ChunkedValue, _ChunkedValuesMixin


class TxtValue(_ChunkedValue):
    pass


class TxtRecord(_ChunkedValuesMixin, Record):
    REFERENCES = (
        'https://datatracker.ietf.org/doc/html/rfc1035',
        'https://datatracker.ietf.org/doc/html/rfc1464',
        'https://datatracker.ietf.org/doc/html/rfc6763',
    )
    _type = 'TXT'
    _value_type = TxtValue


Record.register_type(TxtRecord)
Record.register_validator(ChunkedValueValidator('chunked-value'), types=['TXT'])
