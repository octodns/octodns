#
#
#

from .base import Record
from .chunked import _ChunkedValue, _ChunkedValuesMixin
from .validator import RecordValidator


class SpfRecordTypeValidator(RecordValidator):
    '''
    Validates that the deprecated SPF record type is not used.
    '''

    def validate(self, record_cls, name, fqdn, data, disabled=None):
        return [
            'The SPF record type is DEPRECATED in favor of TXT values and will become an ValidationError in 2.0'
        ]


class SpfRecord(_ChunkedValuesMixin, Record):
    REFERENCES = ('https://datatracker.ietf.org/doc/html/rfc7208',)
    _type = 'SPF'
    _value_type = _ChunkedValue
    VALIDATORS = [SpfRecordTypeValidator('spf-record-type', sets={'strict'})]


Record.register_type(SpfRecord)
