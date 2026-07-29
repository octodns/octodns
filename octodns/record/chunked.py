#
#
#

import re

import dns.exception
import dns.rdata
import dns.rdataclass
import dns.rdatatype
import dns.rdtypes.ANY.TXT

from .base import ValuesMixin
from .rr import RrParseError
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


_unescaped_semicolon_re = re.compile(r'(?<!\\);')

# dnspython already implements RFC 1035 presentation-format parsing/rendering
# (quoting, 255-byte-per-character-string chunking, \"/\\/\DDD escaping) for
# every string-ish rdata type, including TXT. octoDNS's TXT/SPF values are
# handled identically (that's why they share this module), so rather than
# hand-roll our own copy of that logic we delegate to dnspython's TXT rdata
# class for it; the class used doesn't matter as it's the same wire format
# regardless of the actual record type.
_RDCLASS = dns.rdataclass.IN
_RDTYPE = dns.rdatatype.TXT


def _escape_unescaped_semicolons(value):
    '''
    Escapes any ``;`` in `value` that isn't already escaped, leaving
    already-escaped ``\\;`` untouched.

    This is octoDNS's own long-standing internal convention for marking a
    literal ``;`` in its stored values, enforced by ChunkedValueValidator.
    It's not an RFC concept (a bare ``;`` needs no escaping inside a quoted
    RFC 1035 character-string), so it's applied as a separate step on top of
    the real presentation-format handling below, never mixed into it.
    '''
    return _unescaped_semicolon_re.sub('\\\\;', value)


def _parse_presentation_text(value):
    '''
    Parses `value` as RFC 1035 presentation-format rdata text (quoted and/or
    chunked, with \\", \\\\, and \\DDD escapes as dnspython emits/expects)
    and returns the fully decoded, unmarked raw content as a str.

    Raises RrParseError if `value` isn't valid presentation-format text,
    e.g. an unterminated quote or an over-long (>255 byte) single
    character-string.
    '''
    try:
        rdata = dns.rdata.from_text(_RDCLASS, _RDTYPE, value)
    except dns.exception.DNSException as e:
        raise RrParseError() from e
    raw = b''.join(rdata.strings)
    # latin1 maps each byte 0-255 to the identical code point, so this never
    # raises and never loses information; genuinely non-ASCII content is
    # still caught downstream by ChunkedValueValidator at validation time,
    # the same parse-vs-validate split used elsewhere in the codebase
    return raw.decode('latin1')


def _render_presentation_text(chunks):
    '''
    Renders `chunks`, an iterable of <=255-byte bytestrings, as RFC 1035
    presentation-format rdata text: quoted, escaped, and space-joined.
    '''
    rdata = dns.rdtypes.ANY.TXT.TXT(_RDCLASS, _RDTYPE, chunks)
    return rdata.to_text()


class _ChunkedValuesMixin(ValuesMixin):
    CHUNK_SIZE = 255

    def chunked_value(self, value):
        # compat shim for external callers, re-wrap the quoted/chunked
        # text in _value_type so it still behaves like the value types
        # they're used to working with
        chunked = self._value_type(value).chunked(self.CHUNK_SIZE)
        return self._value_type(chunked)

    @property
    def chunked_values(self):
        return [self.chunked_value(v) for v in self.values]


class _ChunkedValue(str):
    VALIDATORS = [chunked_value_validator]

    # default chunk size used by rdata_text, distinct from
    # _ChunkedValuesMixin.CHUNK_SIZE which providers/tests may override
    CHUNK_SIZE = 255

    @classmethod
    def parse_rdata_text(cls, value):
        if not isinstance(value, str) or not value:
            return value
        if isinstance(value, cls):
            # already parsed/processed, nothing to do
            return value

        raw = _parse_presentation_text(value)
        return cls(_escape_unescaped_semicolons(raw))

    @classmethod
    def _schema(cls):
        return {'type': 'string'}

    @classmethod
    def process(cls, values):
        ret = []
        for v in values:
            if isinstance(v, cls):
                # already processed, e.g. round-tripping through
                # record.data, leave it alone
                ret.append(v)
                continue
            if v is None:
                # a missing value: validation (not this lenient step) is
                # the real gate for this, but leave it as None rather than
                # coercing it into the literal string "None"
                ret.append(v)
                continue
            if v and v[:1] == '"':
                # looks like real presentation-format text, e.g. pasted
                # from dig/a zone file. Parse it properly, but stay
                # lenient: this is user-authored YAML, not wire data, and
                # validators (not this step) are the actual gate for
                # malformed content, so fall back to using it as-typed if
                # it doesn't actually parse
                try:
                    v = _escape_unescaped_semicolons(
                        _parse_presentation_text(v)
                    )
                except RrParseError:
                    pass
            ret.append(cls(v))
        return ret

    def chunked(self, chunk_size=None):
        if chunk_size is None:
            chunk_size = self.CHUNK_SIZE
        # un-mark our own ;-convention back to true raw content before
        # handing it to dnspython, which knows nothing about it and would
        # otherwise double-escape the marker's backslash
        raw = self.replace('\\;', ';').encode('latin1')
        n = len(raw)
        chunks = [raw[i : i + chunk_size] for i in range(0, n, chunk_size)]
        text = _render_presentation_text(chunks or [b''])
        # re-mark afterwards: dnspython leaves a bare ; alone since it has
        # no special meaning inside a quoted character-string, but octoDNS's
        # own convention always marks it
        return _escape_unescaped_semicolons(text)

    @property
    def rdata_text(self):
        return self.chunked()

    def template(self, params):
        if '{' not in self:
            return self
        return self.__class__(self.format(**params))
