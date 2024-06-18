#
#
#

import re
from io import StringIO

from .base import ValuesMixin
from .rr import RrParseError


class _ChunkedValuesMixin(ValuesMixin):
    CHUNK_SIZE = 255
    _unescaped_semicolon_re = re.compile(r'\w;')

    @property
    def chunked_values(self):
        values = []
        for v in self.values:
            values.append(v.rdata_text)
        return values

    @property
    def rr_values(self):
        return self.values


def _parse(s, spec_unquoted=False, strict=False):
    whitespace = {' ', '\t', '\n', '\r', '\f', '\v'}

    n = len(s)
    pos = 0
    while pos < n:
        if s[pos] in whitespace:
            # skip whitespace (outside of piece)
            pos += 1
        elif s[pos] == '"':
            # it's a quoted chunk, run until we reach the closing quote,
            # handling escaped quotes as we go
            buf = StringIO()
            pos += 1
            start = pos
            while pos < n:
                i = s.find('"', pos)
                if i == -1:
                    if strict:
                        raise RrParseError()
                    # we didn't find a closing quote, best effort... return
                    # whatever we have left
                    yield s[start:]
                    # we've returned everything
                    pos = n
                elif s[i - 1] == '\\':
                    # it was an escaped quote, grab everything before the escape
                    buf.write(s[start : i - 1])
                    # we'll get the " as part of the next piece
                    start = i
                    pos = i + 1
                else:
                    # it was our closing quote, we have our chunk
                    buf.write(s[start:i])
                    yield buf.getvalue()
                    pos = i + 1
                    break
        elif spec_unquoted:
            # it's not quoted, we want everything up until the next whitespace
            locs = sorted(
                i for i in [s.find(c, pos) for c in whitespace] if i != -1
            )
            if locs:
                i = locs[0]
                # we have our whitespace, everything before it is our chunk
                yield s[pos:i]
                pos = i + 1
            else:
                # we hit the end of s, whatever is left is our chunk
                yield s[pos:]
                pos += 1
                break
        else:
            # it's not quoted, we want everything verbatim, excluding any
            # trailing whitespace
            end = n - 1
            while end >= pos and s[end] in whitespace:
                end -= 1
            yield s[pos : end + 1]
            break


class _ChunkedValue(str):
    _unescaped_semicolon_re = re.compile(r'\w;')

    @classmethod
    def parse_rdata_text(cls, value):
        if not value or not isinstance(value, str):
            return value
        chunks = _parse(value, spec_unquoted=True, strict=True)
        value = ''.join(chunks)
        return value.replace(';', '\\;')

    @classmethod
    def validate(cls, data, _type):
        if not data:
            return ['missing value(s)']
        elif not isinstance(data, (list, tuple)):
            data = (data,)
        reasons = []
        for value in data:
            if cls._unescaped_semicolon_re.search(value):
                reasons.append(f'unescaped ; in "{value}"')
            try:
                value.encode('ascii')
            except UnicodeEncodeError:
                reasons.append(f'non ASCII character in "{value}"')
        return reasons

    @classmethod
    def process(cls, values):
        ret = []
        for value in values:
            value = ''.join(_parse(value))
            ret.append(cls(value))
        return ret

    @property
    def rdata_text(self):
        # TODO: this needs to split & quote
        val = self.replace('"', '\\"')
        chunks = []
        while val:
            chunks.append(val[0 : _ChunkedValuesMixin.CHUNK_SIZE])
            val = val[_ChunkedValuesMixin.CHUNK_SIZE :]
        chunks = '" "'.join(chunks)
        return f'"{chunks}"'
