#
# This file describes the HTTPS records as defined in RFC 9460
# It also supports the 'ech' SvcParam as defined in draft-ietf-tls-svcb-ech-02
#

from .base import Record, ValuesMixin
from .svcb import SvcbValue


class HttpsValue(SvcbValue):
    pass


class HttpsRecord(ValuesMixin, Record):
    _type = 'HTTPS'
    _value_type = HttpsValue


Record.register_type(HttpsRecord)
