#
#
#

from .base import Record
from .chunked import _ChunkedValue, _ChunkedValuesMixin


class SpfRecord(_ChunkedValuesMixin, Record):
    _type = 'SPF'
    _value_type = _ChunkedValue


Record.register_type(SpfRecord)
