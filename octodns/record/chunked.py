#
#
#

import re

import dns.rdata
import dns.rdataclass
import dns.rdatatype
from dns.rdtypes.ANY.TXT import TXT

from .base import (
    ValuesMixin,
    _deprecated_parse_rdata_text,
    _deprecated_rdata_text,
    _value_to_rdata_text_uses_legacy,
    value_to_rdata_text,
)
from .validator import ValidationReason, ValueValidator


class ChunkedValueValidator(ValueValidator):
    '''
    Validates values for TXT/SPF-style chunked strings: present,
    ASCII-only, with no unescaped or double-escaped ``;`` characters.
    '''

    _unescaped_semicolon_re = re.compile(r'\w;')
    _double_escaped_semicolon_re = re.compile(r'\\\\;')

    def validate(self, value_cls, data, _type):
        if not data:
            return [ValidationReason('missing value(s)', validator_id=self.id)]
        elif not isinstance(data, (list, tuple)):
            data = (data,)
        reasons = []
        for value in data:
            if value is None:
                reasons.append(
                    ValidationReason('missing value(s)', validator_id=self.id)
                )
                continue
            if self._unescaped_semicolon_re.search(value):
                reasons.append(
                    ValidationReason(
                        f'unescaped ; in "{value}"', validator_id=self.id
                    )
                )
            if self._double_escaped_semicolon_re.search(value):
                reasons.append(
                    ValidationReason(
                        f'double escaped ; in "{value}"', validator_id=self.id
                    )
                )
            try:
                value.encode('ascii')
            except UnicodeEncodeError:
                reasons.append(
                    ValidationReason(
                        f'non ASCII character in "{value}"',
                        validator_id=self.id,
                    )
                )
        return reasons


chunked_value_validator = ChunkedValueValidator(
    'chunked-value-rfc', sets={'legacy', 'strict'}
)


def _legacy_chunked_value(value, value_type, chunk_size):
    value = value.replace('"', '\\"')
    chunks = []
    i = 0
    n = len(value)
    while i < n:
        c = min(chunk_size, n - i)
        while value[i + c - 1] == '\\':
            c -= 1
        chunks.append(value[i : i + c])
        i += c
    joined = '" "'.join(chunks)
    return value_type(f'"{joined}"')


class _ChunkedValuesMixin(ValuesMixin):
    CHUNK_SIZE = 255

    def chunked_value(self, value):
        return _legacy_chunked_value(value, self._value_type, self.CHUNK_SIZE)

    @property
    def chunked_values(self):
        values = []
        for v in self.values:
            values.append(self.chunked_value(v))
        return values

    @property
    def rr_values(self):
        return self.chunked_values

    def _rdatas(self):
        # ``rr_values`` is retained for backwards compatibility, but consists
        # of presentation-form values. Render from the raw values directly so
        # that RDATA is never quoted and escaped a second time.
        return [
            value_to_rdata_text(value, legacy_value=rr_value)
            for value, rr_value in zip(self.values, self.rr_values)
        ]

    def _legacy_rdatas(self):
        rdatas = []
        for value, rr_value in zip(self.values, self.rr_values):
            if _value_to_rdata_text_uses_legacy(value.__class__):
                rdatas.append(value_to_rdata_text(value, legacy_value=rr_value))
            else:
                rdatas.append(str(rr_value))
        return rdatas


class _ChunkedValue(str):
    VALIDATORS = [chunked_value_validator]

    @classmethod
    def from_raw(cls, value):
        try:
            return value.replace(';', '\\;')
        except AttributeError:
            return value

    @classmethod
    def parse_rdata_text(cls, value):
        _deprecated_parse_rdata_text(cls, f'{cls.__name__}.from_raw()')
        return cls.from_raw(value)

    @classmethod
    def from_rdata_text(cls, rdata):
        '''Convert one RDATA presentation string to octoDNS internal text.

        Character-string bytes are decoded as UTF-8 and semicolons are escaped
        for octoDNS's TXT/SPF internal format.

        :param str rdata: one TXT-style RDATA presentation-format value
        :returns: octoDNS internal-format text
        :rtype: str
        :raises dns.exception.DNSException: if ``rdata`` is not valid TXT
            RDATA presentation text
        :raises UnicodeDecodeError: if parsed character-string bytes are not
            valid UTF-8
        '''
        parsed = dns.rdata.from_text('IN', 'TXT', rdata)
        return b''.join(parsed.strings).decode('utf-8').replace(';', '\\;')

    @classmethod
    def _schema(cls):
        return {'type': 'string'}

    @classmethod
    def process(cls, values):
        ret = []
        for v in values:
            if v and v[0] == '"':
                v = v[1:-1]
            ret.append(cls(v.replace('" "', '')))
        return ret

    @property
    def rdata_text(self):
        _deprecated_rdata_text(self, 'str(value)')
        return self

    def to_rdata_text(self):
        '''Render this octoDNS internal value as RDATA presentation text.

        Valid ASCII input is chunked by octet into character strings of at
        most 255 bytes and rendered by dnspython. Lenient non-ASCII input uses
        the legacy character-based quoting and chunking representation so it
        remains round-trippable as UTF-8 text.

        :returns: one TXT-style RDATA presentation-format string
        :rtype: str
        '''
        raw = self.replace('\\;', ';')
        try:
            value = raw.encode('ascii')
        except UnicodeEncodeError:
            return str(_legacy_chunked_value(self, self.__class__, 255))
        chunks = [value[i : i + 255] for i in range(0, len(value), 255)] or [
            b''
        ]
        return TXT(dns.rdataclass.IN, dns.rdatatype.TXT, chunks).to_text()

    def template(self, params):
        if '{' not in self:
            return self
        return self.__class__(self.format(**params))
