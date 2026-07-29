#
#
#

import re

import dns.exception
import dns.rdata
import dns.rdataclass
import dns.rdatatype
from dns.rdtypes.ANY.TXT import TXT

from ..deprecation import deprecated
from .base import ValuesMixin
from .rr import RrParseError
from .validator import ValidationReason, ValueValidator

# byte length of a single TXT character-string, per RFC 1035 §3.3
_CHARACTER_STRING_LENGTH = 255


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


class _ChunkedValue(str):
    VALIDATORS = [chunked_value_validator]

    @classmethod
    def from_rrs(cls, rdata):
        # strict RFC presentation-format parsing: dnspython handles quoting,
        # escaping, and concatenating multiple character-strings into the
        # single logical value they represent
        try:
            parsed = dns.rdata.from_text(
                dns.rdataclass.IN, dns.rdatatype.TXT, rdata
            )
        except dns.exception.DNSException as e:
            raise RrParseError() from e
        raw = b''.join(parsed.strings).decode('utf-8')
        # restore octoDNS's internal semicolon representation
        return raw.replace(';', '\\;')

    @classmethod
    def parse_rdata_text(cls, value):
        deprecated(
            f'`{cls.__name__}.parse_rdata_text` is DEPRECATED. Use `{cls.__name__}.from_rrs()` instead. Will be removed in 2.0',
            stacklevel=2,
        )
        try:
            return value.replace(';', '\\;')
        except AttributeError:
            return value

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

    def to_rrs(self):
        # strict RFC presentation-format rendering: unescape octoDNS's
        # internal semicolon representation back to a literal `;` (it needs
        # no escaping inside a quoted character-string) and let dnspython
        # handle quoting, escaping, and byte-based 255-octet chunking
        raw = str(self).replace('\\;', ';')
        data = raw.encode('utf-8')
        chunks = [
            data[i : i + _CHARACTER_STRING_LENGTH]
            for i in range(0, len(data), _CHARACTER_STRING_LENGTH)
        ] or [b'']
        rdata = TXT(dns.rdataclass.IN, dns.rdatatype.TXT, chunks)
        return rdata.to_text()

    @property
    def rdata_text(self):
        deprecated(
            f'`{self.__class__.__name__}.rdata_text` is DEPRECATED. Use `{self.__class__.__name__}.to_rrs()` instead. Will be removed in 2.0',
            stacklevel=2,
        )
        return self

    def template(self, params):
        if '{' not in self:
            return self
        return self.__class__(self.format(**params))
