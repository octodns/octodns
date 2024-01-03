#
#
#

import re

from .base import ValuesMixin


class _ChunkedValuesMixin(ValuesMixin):
    CHUNK_SIZE = 255
    _unescaped_semicolon_re = re.compile(r'\w;')

    def chunked_value(self, value):
        value = value.replace('"', '\\"')
        vs = [
            value[i : i + self.CHUNK_SIZE]
            for i in range(0, len(value), self.CHUNK_SIZE)
        ]
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


class _ChunkedValue(str):
    _unescaped_semicolon_re = re.compile(r'\w;')

    @classmethod
    def parse_rdata_text(cls, value):
        try:
            return value.replace(';', '\\;')
        except AttributeError:
            return value

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
        for v in values:
            if v and v[0] == '"':
                v = v[1:-1]
            ret.append(cls(v.replace('" "', '')))
        return ret

    @property
    def rdata_text(self):
        return self
