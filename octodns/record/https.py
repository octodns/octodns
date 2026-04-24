#
# This file describes the HTTPS records as defined in RFC 9460
# It also supports the 'ech' SvcParam as defined in draft-ietf-tls-svcb-ech-02
#

from .base import Record, ValuesMixin
from .svcb import SvcbValue, SvcbValueValidator


class HttpsValue(SvcbValue):
    pass


class HttpsRecord(ValuesMixin, Record):
    REFERENCES = (
        'https://datatracker.ietf.org/doc/html/rfc9460',
        'https://datatracker.ietf.org/doc/html/rfc9461',
        'https://datatracker.ietf.org/doc/html/rfc9462',
    )
    _type = 'HTTPS'
    _value_type = HttpsValue
    VALIDATORS = [SvcbValueValidator('https-value')]


Record.register_type(HttpsRecord)
