#
#
#

import re

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


def _escape_unescaped_semicolons(value):
    '''
    Escapes any ``;`` in `value` that isn't already escaped, leaving
    already-escaped ``\\;`` untouched.
    '''
    return _unescaped_semicolon_re.sub('\\\\;', value)


def _tokenize(value):
    '''
    Tokenizes an RFC 1035 presentation-format rdata string into a sequence
    of (is_quoted, text) pairs, one per whitespace-separated
    character-string. Escaped double quotes (\\") inside a quoted
    character-string are unescaped as part of tokenizing. Raises
    RrParseError if a quoted character-string is never closed.
    '''
    n = len(value)
    i = 0
    while i < n:
        c = value[i]
        if c.isspace():
            # whitespace between character-strings, skip over it
            i += 1
            continue
        if c == '"':
            # quoted character-string, run until we hit an unescaped
            # closing quote
            i += 1
            start = i
            buf = []
            while True:
                j = value.find('"', i)
                if j == -1:
                    # never found a closing quote
                    raise RrParseError()
                if value[j - 1] == '\\':
                    # it was an escaped quote, keep the " and keep looking
                    # for the real closing quote
                    buf.append(value[start : j - 1])
                    buf.append('"')
                    i = j + 1
                    start = i
                else:
                    # found our closing quote
                    buf.append(value[start:j])
                    i = j + 1
                    break
            yield True, ''.join(buf)
        else:
            # unquoted character-string, run until whitespace or a quote
            start = i
            while i < n and not value[i].isspace() and value[i] != '"':
                i += 1
            yield False, value[start:i]


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

        tokens = list(_tokenize(value))
        if not tokens:
            # nothing but whitespace
            return cls('')
        elif len(tokens) == 1:
            # a single character-string, quoted or not, is unambiguous
            text = tokens[0][1]
        elif all(is_quoted for is_quoted, _ in tokens):
            # multiple quoted character-strings, e.g. a previously chunked
            # value, concatenate them to reconstruct the original value
            text = ''.join(text for _, text in tokens)
        else:
            # multiple unquoted, and/or a mix of quoted & unquoted,
            # character-strings are ambiguous to concatenate without
            # loss, we don't guess
            raise RrParseError()

        return cls(_escape_unescaped_semicolons(text))

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
            if v and v[0] == '"':
                v = v[1:-1]
            ret.append(cls(v.replace('" "', '')))
        return ret

    def chunked(self, chunk_size=None):
        if chunk_size is None:
            chunk_size = self.CHUNK_SIZE
        value = self.replace('"', '\\"')
        vs = []
        i = 0
        n = len(value)
        # until we've processed the whole string
        while i < n:
            # start with a full chunk size
            c = min(chunk_size, n - i)
            # make sure that we don't break on escape chars
            while value[i + c - 1] == '\\':
                c -= 1
            # we have our chunk now
            vs.append(value[i : i + c])
            # and can step over it
            i += c
        vs = '" "'.join(vs)
        # a plain str, not self.__class__: this is presentation-format
        # rdata text, not an internal/processed value, and returning cls
        # here would make parse_rdata_text's already-processed shortcut
        # misfire on it
        return f'"{vs}"'

    @property
    def rdata_text(self):
        return self.chunked()

    def template(self, params):
        if '{' not in self:
            return self
        return self.__class__(self.format(**params))
