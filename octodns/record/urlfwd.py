#
#
#

from ..equality import EqualityTupleMixin
from .base import Record, ValuesMixin, unquote
from .rr import RrParseError


class UrlfwdValue(EqualityTupleMixin, dict):
    VALID_CODES = (301, 302)
    VALID_MASKS = (0, 1, 2)
    VALID_QUERY = (0, 1)

    @classmethod
    def parse_rdata_text(self, value):
        try:
            path, target, code, masking, query = value.split(' ')
        except ValueError:
            raise RrParseError()
        try:
            code = int(code)
        except ValueError:
            pass
        try:
            masking = int(masking)
        except ValueError:
            pass
        try:
            query = int(query)
        except ValueError:
            pass
        path = unquote(path)
        target = unquote(target)
        return {
            'path': path,
            'target': target,
            'code': code,
            'masking': masking,
            'query': query,
        }

    @classmethod
    def validate(cls, data, _type):
        reasons = []
        for value in data:
            try:
                code = int(value['code'])
                if code not in cls.VALID_CODES:
                    reasons.append(f'unrecognized return code "{code}"')
            except KeyError:
                reasons.append('missing code')
            except ValueError:
                reasons.append(f'invalid return code "{value["code"]}"')
            try:
                masking = int(value['masking'])
                if masking not in cls.VALID_MASKS:
                    reasons.append(f'unrecognized masking setting "{masking}"')
            except KeyError:
                reasons.append('missing masking')
            except ValueError:
                reasons.append(f'invalid masking setting "{value["masking"]}"')
            try:
                query = int(value['query'])
                if query not in cls.VALID_QUERY:
                    reasons.append(f'unrecognized query setting "{query}"')
            except KeyError:
                reasons.append('missing query')
            except ValueError:
                reasons.append(f'invalid query setting "{value["query"]}"')
            for k in ('path', 'target'):
                if k not in value:
                    reasons.append(f'missing {k}')
        return reasons

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    def __init__(self, value):
        super().__init__(
            {
                'path': value['path'],
                'target': value['target'],
                'code': int(value['code']),
                'masking': int(value['masking']),
                'query': int(value['query']),
            }
        )

    @property
    def path(self):
        return self['path']

    @path.setter
    def path(self, value):
        self['path'] = value

    @property
    def target(self):
        return self['target']

    @target.setter
    def target(self, value):
        self['target'] = value

    @property
    def code(self):
        return self['code']

    @code.setter
    def code(self, value):
        self['code'] = value

    @property
    def masking(self):
        return self['masking']

    @masking.setter
    def masking(self, value):
        self['masking'] = value

    @property
    def query(self):
        return self['query']

    @query.setter
    def query(self, value):
        self['query'] = value

    @property
    def rdata_text(self):
        return f'"{self.path}" "{self.target}" {self.code} {self.masking} {self.query}'

    def _equality_tuple(self):
        return (self.path, self.target, self.code, self.masking, self.query)

    def __hash__(self):
        return hash(
            (self.path, self.target, self.code, self.masking, self.query)
        )

    def __repr__(self):
        return f'"{self.path}" "{self.target}" {self.code} {self.masking} {self.query}'


class UrlfwdRecord(ValuesMixin, Record):
    _type = 'URLFWD'
    _value_type = UrlfwdValue


Record.register_type(UrlfwdRecord)
