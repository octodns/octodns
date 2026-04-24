#
#
#

from ..deprecation import deprecated
from .base import Record
from .chunked import ChunkedValueValidator, _ChunkedValue, _ChunkedValuesMixin


class SpfRecord(_ChunkedValuesMixin, Record):
    REFERENCES = ('https://datatracker.ietf.org/doc/html/rfc7208',)
    _type = 'SPF'
    _value_type = _ChunkedValue

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        deprecated(
            'The SPF record type is DEPRECATED in favor of TXT values and will become an ValidationError in 2.0',
            stacklevel=99,
        )


Record.register_type(SpfRecord)
Record.register_validator(ChunkedValueValidator('chunked-value'), types=['SPF'])
