#
#
#

from .base import Record, readonly
from .chunked import _ChunkedValue, _ChunkedValuesMixin


class TxtValue(_ChunkedValue):
    pass


class TxtRecord(_ChunkedValuesMixin, Record):
    _type = readonly('TXT')
    _value_type = TxtValue


Record.register_type(TxtRecord)
