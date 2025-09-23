#
#
#

from collections import defaultdict
from copy import deepcopy
from itertools import chain
from logging import getLogger

from jsonschema import Draft202012Validator

from ..context import ContextDict
from ..deprecation import deprecated
from ..equality import EqualityTupleMixin
from ..idna import IdnaError, idna_decode, idna_encode
from .change import Update
from .exception import RecordException, ValidationError


def unquote(s):
    if s and s[0] in ('"', "'"):
        return s[1:-1]
    return s


class Record(EqualityTupleMixin):
    log = getLogger('Record')

    _CLASSES = {}
    _VALIDATORS = {}

    @classmethod
    def register_type(cls, _class, _type=None):
        if _type is None:
            _type = _class._type
        existing = cls._CLASSES.get(_type)
        if existing:
            module = existing.__module__
            name = existing.__name__
            msg = f'Type "{_type}" already registered by {module}.{name}'
            raise RecordException(msg)
        cls._CLASSES[_type] = _class

        # see if there's a data schema
        schema = _class.data_schema()
        if schema:
            # data_schema is a flag for using the updated validation mechinism,
            # so use the schema based name validation as well
            cls._VALIDATORS[_type] = (
                Draft202012Validator(schema=_class.name_schema()),
                Draft202012Validator(schema=schema),
            )

    @classmethod
    def registered_types(cls):
        return cls._CLASSES

    @classmethod
    def new(cls, zone, name, data, source=None, lenient=False):
        reasons = []
        try:
            name = idna_encode(str(name))
        except IdnaError as e:
            # convert the error into a reason
            reasons.append(str(e))
            name = str(name)

        if ' ' in name or '\t' in name:
            reasons.append('invalid record, whitespace is not allowed')

        fqdn = f'{name}.{zone.name}' if name else zone.name
        context = getattr(data, 'context', None)
        try:
            _type = data['type']
        except KeyError:
            msg = f'Invalid record {idna_decode(fqdn)}, missing type'
            if context:
                msg += f', {context}'
            raise Exception(msg)
        try:
            _class = cls._CLASSES[_type]
        except KeyError:
            msg = f'Unknown record type: "{_type}"'
            if context:
                msg += f', {context}'
            raise Exception(msg)

        if _type in cls._VALIDATORS:
            # TODO: this should live somewhere else
            # new jsonschema based validaton
            name_validator, data_validator = cls._VALIDATORS.get(_type)
            errors = chain(
                name_validator.iter_errors({'name': name, 'fqdn': fqdn}),
                data_validator.iter_errors(data),
            )
            for error in errors:
                # some of the jsonschema error messages are opaque and useless
                # to end uses, this provides a mechinism to translate them.
                schema = error.schema
                try:
                    message = schema['$error_message']
                    cls.log.debug('new: $error_message=`%s`, instance=%s', message, error.instance)
                except KeyError:
                    path = '.'.join(str(p) for p in error.schema_path)
                    try:
                        messages = schema['$error_messages']
                        cls.log.debug('new: $error_messages=%s, path=%s', messages, path)
                        message = messages[path]
                        cls.log.debug('new: $error_message=`%sr`, instance=%s', message, error.instance)
                        message = message.format(instance=error.instance)
                        cls.log.debug('new: $error_message.format=`%sr`', message)
                    except KeyError:
                        message = error.message
                        cls.log.debug('new: error.message=`%sr`', message)
                else:
                    instance = error.instance
                    message = message, instance=error.instance)
                    cls.log.debug('new: $error_message.format=`%s`', message)
                reasons.append(message)
        else:
            # original .validate
            reasons.extend(_class.validate(name, fqdn, data))

        try:
            lenient |= data['octodns']['lenient']
        except KeyError:
            pass
        if reasons:
            if lenient:
                cls.log.warning(
                    ValidationError.build_message(fqdn, reasons, context)
                )
            else:
                raise ValidationError(fqdn, reasons, context)
        return _class(zone, name, data, source=source, context=context)

    @classmethod
    def name_schema(cls):
        # https://github.com/ypcrts/fqdn?tab=readme-ov-file#ietf-specification
        # https://datatracker.ietf.org/doc/html/rfc1034
        # https://datatracker.ietf.org/doc/html/rfc1035
        return {
            'properties': {
                'name': {'type': 'string'},
                'fqdn': {'type': 'string', 'maxLength': 253,
                         '$error_message': 'invalid fqdn, "{instance} is too long at {len(instance)}, max is 253"'},
            },
            'allOf': [
                {
                    'properties': {
                        'name': {
                            'not': {'const': '@'},
                            # TODO: quote name
                            '$error_message': 'invalid name "@", use "" instead',
                        }
                    }
                },
                {
                    'properties': {
                        'name': {
                            'not': {'pattern': r'[^\.]{63}'},
                            '$error_message': 'invalid label, too long, max is 63',
                        }
                    }
                },
                {
                    'properties': {
                        'name': {
                            'not': {'pattern': r'\.\.'},
                            '$error_message': 'invalid name, double `.`',
                        }
                    }
                },
                {
                    'properties': {
                        'name': {
                            'not': {'pattern': r'\.$'},
                            '$error_message': 'invalid name, double `.`',
                        }
                    }
                },
            ],
            'required': ['name', 'fqdn'],
        }

    def TODO_remove(cls):
        class_schemas = []
        for _type, schema in cls._SCHEMAS.items():
            class_schemas.append(
                {
                    'if': {'properties': {'type': {'enum': [_type]}}},
                    'then': {
                        'title': _type,
                        'properties': {
                            'type': {},
                            'ttl': {
                                'type': 'integer',
                                'minimum': 0,
                                'maximum': 86400,
                            },
                            'value': schema,
                        },
                        'required': ['ttl', 'type', 'value'],
                        "unevaluatedProperties": False,
                    },
                }
            )

        if class_schemas:
            schema['allOf'] = class_schemas

        # validate(schema=schema, instance={
        #    'type': 'A',
        #    'ttl': 42,
        #    'value': 'nope',
        # }, format_checker=Draft202012Validator.FORMAT_CHECKER)

        return schema

    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = []
        if name == '@':
            reasons.append('invalid name "@", use "" instead')
        n = len(fqdn)
        if n > 253:
            reasons.append(
                f'invalid fqdn, "{idna_decode(fqdn)}" is too long at {n} '
                'chars, max is 253'
            )
        for label in name.split('.'):
            n = len(label)
            if n > 63:
                reasons.append(
                    f'invalid label, "{label}" is too long at {n}'
                    ' chars, max is 63'
                )
        # in the case of endswith there's an implicit second . from the Zone
        if '..' in name or name.endswith('.'):
            reasons.append(f'invalid name, double `.` in "{idna_decode(fqdn)}"')
        # TODO: look at the idna lib for a lot more potential validations...
        try:
            ttl = int(data['ttl'])
            if ttl < 0:
                reasons.append('invalid ttl')
        except KeyError:
            reasons.append('missing ttl')
        try:
            if data['octodns']['healthcheck']['protocol'] not in (
                'HTTP',
                'HTTPS',
                'ICMP',
                'TCP',
                'UDP',
            ):
                reasons.append('invalid healthcheck protocol')
        except KeyError:
            pass
        return reasons

    @classmethod
    def from_rrs(cls, zone, rrs, lenient=False, source=None):
        # group records by name & type so that multiple rdatas can be combined
        # into a single record when needed
        grouped = defaultdict(list)
        for rr in rrs:
            grouped[(rr.name, rr._type)].append(rr)

        records = []
        # walk the grouped rrs converting each one to data and then create a
        # record with that data
        for _, rrs in sorted(grouped.items()):
            rr = rrs[0]
            name = zone.hostname_from_fqdn(rr.name)
            _class = cls._CLASSES[rr._type]
            data = _class.data_from_rrs(rrs)
            record = Record.new(
                zone, name, data, lenient=lenient, source=source
            )
            records.append(record)

        return records

    @classmethod
    def parse_rdata_texts(cls, rdatas):
        return [cls._value_type.parse_rdata_text(r) for r in rdatas]

    def __init__(self, zone, name, data, source=None, context=None):
        self.zone = zone
        if name:
            # internally everything is idna
            self.name = idna_encode(str(name))
            # we'll keep a decoded version around for logs and errors
            self.decoded_name = idna_decode(self.name)
        else:
            self.name = self.decoded_name = name
        self.log.debug(
            '__init__: zone.name=%s, type=%11s, name=%s',
            zone.decoded_name,
            self.__class__.__name__,
            self.decoded_name,
        )
        self.source = source
        self.context = context
        self.ttl = int(data['ttl'])

        self.octodns = data.get('octodns', {})

    @property
    def _octodns(self):
        deprecated(
            '`Record._octodns` is DEPRECATED. Use `Record.octodns` instead. Will be removed in 2.0',
            stacklevel=1,
        )
        return self.octodns

    @_octodns.setter
    def _octodns(self, val):
        deprecated(
            '`Record._octodns` is DEPRECATED. Use `Record.octodns` instead. Will be removed in 2.0',
            stacklevel=1,
        )
        self.octodns = val

    def _data(self):
        ret = {'ttl': self.ttl}
        if self.octodns:
            ret['octodns'] = deepcopy(self.octodns)
        if self.context:
            return ContextDict(ret, context=self.context)
        return ret

    @property
    def data(self):
        return self._data()

    @property
    def fqdn(self):
        # TODO: these should be calculated and set in __init__ rather than on
        # each use
        if self.name:
            return f'{self.name}.{self.zone.name}'
        return self.zone.name

    @property
    def decoded_fqdn(self):
        if self.decoded_name:
            return f'{self.decoded_name}.{self.zone.decoded_name}'
        return self.zone.decoded_name

    @property
    def ignored(self):
        return self.octodns.get('ignored', False)

    @property
    def excluded(self):
        return self.octodns.get('excluded', [])

    @property
    def included(self):
        return self.octodns.get('included', [])

    def healthcheck_host(self, value=None):
        healthcheck = self.octodns.get('healthcheck', {})
        protocol = self.healthcheck_protocol
        if protocol not in ('HTTP', 'HTTPS'):
            return None
        return healthcheck.get('host', self.fqdn[:-1]) or value

    @property
    def healthcheck_path(self):
        healthcheck = self.octodns.get('healthcheck', {})
        protocol = self.healthcheck_protocol
        if protocol not in ('HTTP', 'HTTPS'):
            return None
        try:
            return healthcheck['path']
        except KeyError:
            return '/_dns'

    @property
    def healthcheck_protocol(self):
        try:
            return self.octodns['healthcheck']['protocol']
        except KeyError:
            return 'HTTPS'

    @property
    def healthcheck_port(self):
        if self.healthcheck_protocol == 'ICMP':
            return None
        try:
            return int(self.octodns['healthcheck']['port'])
        except KeyError:
            return 443

    @property
    def lenient(self):
        return self.octodns.get('lenient', False)

    def changes(self, other, target):
        # We're assuming we have the same name and type if we're being compared
        if self.ttl != other.ttl:
            return Update(self, other)

    def copy(self, zone=None):
        # data, via _data(), will preserve context
        data = self.data
        data['type'] = self._type

        return Record.new(
            zone if zone else self.zone,
            self.name,
            data,
            self.source,
            lenient=True,
        )

    # NOTE: we're using __hash__ and ordering methods that consider Records
    # equivalent if they have the same name & _type. Values are ignored. This
    # is useful when computing diffs/changes.

    def __hash__(self):
        return f'{self.name}:{self._type}'.__hash__()

    def _equality_tuple(self):
        return (self.name, self._type)

    def __repr__(self):
        # Make sure this is always overridden
        raise NotImplementedError('Abstract base class, __repr__ required')


class ValuesMixin(object):

    @classmethod
    def data_schema(cls):
        value_type = cls._value_type
        if not hasattr(value_type, 'schema'):
            return

        return {
            '$schema': 'https://json-schema.org/draft/2020-12/schema',
            '$defs': {'schema': value_type.schema()},
            'title': cls._type,
            'properties': {
                # TODO: what schema validations make sense for these
                'octodns': {},
                'geo': {},
                'dynamic': {},
                'type': {'const': cls._type},
                'ttl': {'type': 'integer', 'minimum': 0, 'maximum': 86400},
                'value': {'$ref': '#/$defs/schema'},
                'values': {
                    'type': 'array',
                    'items': {'$ref': '#/$defs/schema'},
                    'minItems': 1,
                },
            },
            'required': ['ttl', 'type'],
            'anyOf': [{'required': ['value']}, {'required': ['values']}],
            "unevaluatedProperties": False,
            '$error_messages': {
                'anyOf': "one of 'value' or 'values' is a required property"
            },
        }

    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = super().validate(name, fqdn, data)

        values = data.get('values', data.get('value', []))
        values = values if isinstance(values, (list, tuple)) else [values]

        reasons.extend(cls._value_type.validate(values, cls._type))

        return reasons

    @classmethod
    def data_from_rrs(cls, rrs):
        # type and TTL come from the first rr
        rr = rrs[0]
        # values come from parsing the rdata portion of all rrs
        values = [cls._value_type.parse_rdata_text(rr.rdata) for rr in rrs]
        return {'ttl': rr.ttl, 'type': rr._type, 'values': values}

    def __init__(self, zone, name, data, source=None, context=None):
        super().__init__(zone, name, data, source=source, context=context)

        values = data.get('values', data.get('value', []))
        values = values if isinstance(values, (list, tuple)) else [values]
        self.values = sorted(self._value_type.process(values))

    def changes(self, other, target):
        if self.values != other.values:
            return Update(self, other)
        return super().changes(other, target)

    def _data(self):
        ret = super()._data()
        if len(self.values) == 1:
            v = self.values[0]
            if v:
                ret['value'] = getattr(v, 'data', v)
        else:
            values = [getattr(v, 'data', v) for v in self.values if v]
            if len(values) == 1:
                ret['value'] = values[0]
            else:
                ret['values'] = values

        return ret

    @property
    def rr_values(self):
        return self.values

    @property
    def rrs(self):
        return (
            self.fqdn,
            self.ttl,
            self._type,
            [v.rdata_text for v in self.rr_values],
        )

    def __repr__(self):
        values = "', '".join([str(v) for v in self.values])
        klass = self.__class__.__name__
        octodns = ''
        if self.octodns:
            octodns = f', {self.octodns}'
        return f"<{klass} {self._type} {self.ttl}, {self.decoded_fqdn}, ['{values}']{octodns}>"


class ValueMixin(object):

    @classmethod
    def data_schema(cls):
        value_type = cls._value_type
        if not hasattr(value_type, 'schema'):
            return

        return {
            '$schema': 'https://json-schema.org/draft/2020-12/schema',
            'title': cls._type,
            'properties': {
                # TODO: what schema validations make sense for octodns?
                'octodns': {},
                'type': {'const': cls._type},
                'ttl': {'type': 'integer', 'minimum': 0, 'maximum': 86400},
                'value': value_type.schema(),
            },
            'required': ['ttl', 'type', 'value'],
            "unevaluatedProperties": False,
        }

    @classmethod
    def validate(cls, name, fqdn, data):
        reasons = super().validate(name, fqdn, data)
        reasons.extend(
            cls._value_type.validate(data.get('value', None), cls._type)
        )
        return reasons

    @classmethod
    def data_from_rrs(cls, rrs):
        # single value, so single rr only...
        rr = rrs[0]
        return {
            'ttl': rr.ttl,
            'type': rr._type,
            'value': cls._value_type.parse_rdata_text(rr.rdata),
        }

    def __init__(self, zone, name, data, source=None, context=None):
        super().__init__(zone, name, data, source=source, context=context)
        self.value = self._value_type.process(data['value'])

    def changes(self, other, target):
        if self.value != other.value:
            return Update(self, other)
        return super().changes(other, target)

    def _data(self):
        ret = super()._data()
        ret['value'] = getattr(self.value, 'data', self.value)
        return ret

    @property
    def rrs(self):
        return self.fqdn, self.ttl, self._type, [self.value.rdata_text]

    def __repr__(self):
        klass = self.__class__.__name__
        octodns = ''
        if self.octodns:
            octodns = f', {self.octodns}'
        return f'<{klass} {self._type} {self.ttl}, {self.decoded_fqdn}, {self.value}{octodns}>'
