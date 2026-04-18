#
#
#

'''
Build a JSON Schema describing octoDNS YAML zone files.

The schema is generated from the record classes currently registered with
`Record.registered_types()` so it stays in sync with the code. Value classes
expose an optional `_schema` classmethod that returns the JSON Schema fragment
for a single value; record-level shape (name keys, record lists, ttl,
octodns metadata) is assembled here.

This schema is intended for external consumers (IDEs, CI lint, SchemaStore),
not for octoDNS's own validation, which continues to handle error reporting
with source context.
'''

from ..record import Record
from ..record.base import ValueMixin
from ..record.dynamic import _DynamicMixin
from ..record.geo import _GeoMixin

# When a value class doesn't yet expose `_schema`, fall back to permissive.
# Individual record types will add `_schema` as coverage grows.
_DEFAULT_VALUE_SCHEMA = True


_OCTODNS_META = {
    'type': 'object',
    # providers (in external packages) can add their own fields
    'additionalProperties': True,
    'properties': {
        'ignored': {'type': 'boolean'},
        'lenient': {'type': 'boolean'},
        'excluded': {'type': 'array', 'items': {'type': 'string'}},
        'included': {'type': 'array', 'items': {'type': 'string'}},
        'healthcheck': {
            'type': 'object',
            'additionalProperties': True,
            'properties': {
                'protocol': {
                    'type': 'string',
                    'enum': ['HTTP', 'HTTPS', 'ICMP', 'TCP', 'UDP'],
                },
                'host': {'type': ['string', 'null']},
                'path': {'type': 'string'},
                'port': {'type': 'integer', 'minimum': 0, 'maximum': 65535},
            },
        },
    },
}


def _value_schema(value_type):
    schema_fn = getattr(value_type, '_schema', None)
    if schema_fn is None:
        return _DEFAULT_VALUE_SCHEMA
    return schema_fn()


def _value_props(record_class):
    value_schema = _value_schema(record_class._value_type)
    if issubclass(record_class, ValueMixin):
        props = {'value': value_schema}
    else:
        # ValuesMixin — accepts either `values` (list) or `value` (single)
        props = {
            'value': value_schema,
            'values': {'type': 'array', 'items': value_schema, 'minItems': 1},
        }
    if issubclass(record_class, _DynamicMixin):
        props['dynamic'] = _DynamicMixin._schema(value_schema)
    if issubclass(record_class, _GeoMixin):
        props['geo'] = _GeoMixin._schema(value_schema)
    return props


def _type_branch(type_name, record_class):
    return {
        'if': {
            'properties': {'type': {'const': type_name}},
            'required': ['type'],
        },
        'then': {'properties': _value_props(record_class)},
    }


def _record_def():
    types = sorted(Record.registered_types().keys())
    return {
        'type': 'object',
        'required': ['type'],
        # ttl intentionally not required — YamlProvider fills in default_ttl
        # for records that omit it
        'properties': {
            'type': {'type': 'string', 'enum': types},
            'ttl': {'type': 'integer', 'minimum': 0},
            'octodns': {'$ref': '#/$defs/octodns_meta'},
        },
        # tolerate per-type fields (value, values, dynamic, geo, ...) and
        # provider-specific extras; the type-specific if/then branches add
        # the real constraints
        'additionalProperties': True,
        'allOf': [
            _type_branch(t, c)
            for t, c in sorted(Record.registered_types().items())
        ],
    }


def build_zone_schema():
    '''Return a dict describing the JSON Schema for an octoDNS zone file.'''
    return {
        '$schema': 'https://json-schema.org/draft/2020-12/schema',
        'title': 'octoDNS zone file',
        'description': (
            'Schema for an octoDNS zone YAML file: a mapping of record names '
            'to a record or list of records.'
        ),
        'type': 'object',
        'additionalProperties': {
            'oneOf': [
                {'$ref': '#/$defs/record'},
                {
                    'type': 'array',
                    'items': {'$ref': '#/$defs/record'},
                    'minItems': 1,
                },
            ]
        },
        '$defs': {'record': _record_def(), 'octodns_meta': _OCTODNS_META},
    }
