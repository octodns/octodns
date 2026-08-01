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


class _ChunkedValuesMixin(ValuesMixin):
    CHUNK_SIZE = 255

    def chunked_value(self, value):
        value = value.replace('"', '\\"')
        vs = []
        i = 0
        n = len(value)
        # until we've processed the whole string
        while i < n:
            # start with a full chunk size
            c = min(self.CHUNK_SIZE, n - i)
            # make sure that we don't break on escape chars
            while value[i + c - 1] == '\\':
                c -= 1
            # we have our chunk now
            vs.append(value[i : i + c])
            # and can step over if
            i += c
        vs = '" "'.join(vs)
        return self._value_type(f'"{vs}"')

    @property
    def chunked_values(self):
        values = []
        for v in self.values:
            values.append(self.chunked_value(v))
        return values

    @property
    def rr_values(self):
        return self.chunked_values

    @property
    def rrs(self):
        # ``rr_values`` is retained for backwards compatibility, but consists
        # of presentation-form values. Render from the raw values directly so
        # that RDATA is never quoted and escaped a second time.
        return (
            self.fqdn,
            self.ttl,
            self._type,
            [value.to_rrs() for value in self.values],
        )


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
        _deprecated_parse_rdata_text(cls)
        return cls.from_raw(value)

    @classmethod
    def from_rrs(cls, rdata):
        parsed = dns.rdata.from_text('IN', 'TXT', rdata)
        return b''.join(parsed.strings).decode('ascii').replace(';', '\\;')

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
        _deprecated_rdata_text(self)
        return self

    def to_rrs(self):
        value = self.replace('\\;', ';').encode('ascii')
        chunks = [value[i : i + 255] for i in range(0, len(value), 255)] or [
            b''
        ]
        return TXT(dns.rdataclass.IN, dns.rdatatype.TXT, chunks).to_text()

    def template(self, params):
        if '{' not in self:
            return self
        return self.__class__(self.format(**params))
