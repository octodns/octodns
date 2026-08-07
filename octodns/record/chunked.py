#
#
#

import re

import dns.exception
import dns.rdata
import dns.rdataclass
import dns.rdatatype
import dns.tokenizer
from dns.rdtypes.ANY.TXT import TXT

from .base import (
    ValuesMixin,
    _deprecated_parse_rdata_text,
    _deprecated_rdata_text,
    _value_to_rdata_text_uses_legacy,
    value_to_rdata_text,
)
from .rr import RdataParseError
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


def _scan_rdata_tokens(rdata):
    '''Tokenize presentation text, reporting whether a comment was dropped.

    An unquoted ``;`` starts a master-file comment, so the tokenizer silently
    discards the remainder of the value. Surfacing that lets callers recognize
    input that isn't really presentation format.

    :param str rdata: presentation-format text to scan
    :returns: the non-comment tokens and whether a comment was seen
    :rtype: tuple
    '''
    tokenizer = dns.tokenizer.Tokenizer(rdata)
    tokens = []
    saw_comment = False
    while True:
        token = tokenizer.get(want_comment=True)
        if token.ttype == dns.tokenizer.EOF:
            break
        elif token.ttype == dns.tokenizer.COMMENT:
            saw_comment = True
        elif token.ttype != dns.tokenizer.EOL:
            tokens.append(token)
    return tokens, saw_comment


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
    '''Legacy record-level chunking compatibility for TXT/SPF values.

    ``CHUNK_SIZE``, ``chunked_value()``, ``chunked_values``, and ``rr_values``
    are used by the deprecated ``record.rrs`` representation. New-style
    values rendered by ``to_rrset()`` always use the value-level conversion's
    255-octet DNS limit instead.

    .. deprecated:: 1.22.0
       These record-level chunking hooks will be removed with ``record.rrs``
       in 2.0.
    '''

    CHUNK_SIZE = 255

    def chunked_value(self, value):
        '''Render one value with the legacy record-level chunk size.'''
        return _legacy_chunked_value(value, self._value_type, self.CHUNK_SIZE)

    @property
    def chunked_values(self):
        '''Render all values with the legacy record-level chunk size.'''
        values = []
        for v in self.values:
            values.append(self.chunked_value(v))
        return values

    @property
    def rr_values(self):
        '''Return presentation-form values for the deprecated ``rrs`` API.'''
        return self.chunked_values

    def _rdatas(self):
        if _value_to_rdata_text_uses_legacy(self._value_type):
            # Legacy overrides historically receive the presentation-form
            # objects exposed by ``rr_values``. Only evaluate those objects
            # when the compatibility dispatch actually needs them.
            return [value_to_rdata_text(value) for value in self.rr_values]
        return [value_to_rdata_text(value) for value in self.values]

    def _legacy_rdatas(self):
        rdatas = []
        for rr_value in self.rr_values:
            if _value_to_rdata_text_uses_legacy(rr_value.__class__):
                rdatas.append(value_to_rdata_text(rr_value))
            else:
                rdatas.append(str(rr_value))
        return rdatas


class _ChunkedValue(str):
    VALIDATORS = [chunked_value_validator]

    @classmethod
    def normalize_raw_text(cls, value):
        '''Normalize unescaped TXT/SPF provider text for octoDNS records.

        :param object value: raw provider value, normally a string
        :returns: octoDNS internal text with semicolons escaped, or a
            non-string value unchanged for legacy compatibility
        '''
        try:
            return value.replace(';', '\\;')
        except AttributeError:
            return value

    def to_raw_text(self):
        '''Convert octoDNS internal TXT/SPF text to raw provider text.

        This is the inverse of :meth:`normalize_raw_text` for valid internal
        values. It removes octoDNS's semicolon escaping without adding RDATA
        presentation-format quoting or chunking.

        :returns: unescaped TXT/SPF text suitable for a raw-text provider
        :rtype: str
        '''
        return self.replace('\\;', ';')

    @classmethod
    def parse_rdata_text(cls, value):
        _deprecated_parse_rdata_text(
            cls, f'{cls.__name__}.normalize_raw_text()'
        )
        return cls.normalize_raw_text(value)

    @classmethod
    def from_rdata_text(cls, rdata):
        '''Convert one RDATA presentation string to octoDNS internal text.

        Character-string bytes are decoded as UTF-8 and semicolons are escaped
        for octoDNS's TXT/SPF internal format.

        Wholly unquoted input is treated as legacy raw text whenever it carries
        a signal that it isn't presentation format: multiple character-string
        tokens, so that spaces are not silently discarded, or an unquoted ``;``,
        so that the remainder of values such as DKIM keys is not silently
        dropped as a master-file comment.

        :param str rdata: one TXT-style RDATA presentation-format value
        :returns: octoDNS internal-format text
        :rtype: str
        :raises octodns.record.rr.RdataParseError: if ``rdata`` is not valid
            TXT RDATA presentation text or its character-string bytes are not
            valid UTF-8
        '''
        try:
            tokens, saw_comment = _scan_rdata_tokens(rdata)
            if all(token.is_identifier() for token in tokens) and (
                len(tokens) > 1 or saw_comment
            ):
                return cls.normalize_raw_text(rdata)
            parsed = dns.rdata.from_text('IN', 'TXT', rdata)
            return b''.join(parsed.strings).decode('utf-8').replace(';', '\\;')
        except (dns.exception.DNSException, UnicodeDecodeError) as error:
            raise RdataParseError() from error

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
        the legacy character-based quoting and chunking representation. That
        compatibility output is round-trippable only when every emitted
        character-string fits within the 255-octet DNS limit as UTF-8.

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
