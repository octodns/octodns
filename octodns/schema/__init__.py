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


# 3rd-party providers register custom record types with names like
# `Route53/ELB` or `octodns_route53.Route53/EC2` — an optional dotted module
# path, a slash, then the type name. These types aren't known when the
# schema is generated (e.g. SchemaStore publishes a static snapshot), so
# matching this pattern puts the record in a permissive catch-all branch.
_THIRD_PARTY_TYPE_PATTERN = r'^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*/[A-Za-z_]\w*$'


# Syntactic constraints on record name keys. Mirrors the generic checks in
# `Record.validate` (octodns/record/base.py) that don't require zone context:
# no "@", no label longer than 63 chars, no "..", no trailing ".". The fqdn
# length check (253) needs the zone name and stays imperative-only.
#
# Guarded by `if type: string` because YAML loaders may hand us non-string
# keys (e.g. numeric labels in reverse zones parse as ints); octoDNS itself
# stringifies names before imperative validation, so the schema stays out of
# the way for non-string keys.
_NAME_SCHEMA = {
    'if': {'type': 'string'},
    'then': {
        'allOf': [
            {'not': {'const': '@'}},
            {'not': {'pattern': r'\.\.'}},
            {'not': {'pattern': r'\.$'}},
            {'not': {'pattern': r'[^.]{64}'}},
        ]
    },
}


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


def _third_party_branch():
    # permissive catch-all for 3rd-party types (see _THIRD_PARTY_TYPE_PATTERN)
    return {
        'if': {
            'properties': {'type': {'pattern': _THIRD_PARTY_TYPE_PATTERN}},
            'required': ['type'],
        },
        'then': {
            'properties': {
                'value': True,
                'values': True,
                'dynamic': True,
                'geo': True,
            }
        },
    }


def _record_def():
    types = sorted(Record.registered_types().keys())
    return {
        'type': 'object',
        'required': ['type'],
        # ttl intentionally not required — YamlProvider fills in default_ttl
        # for records that omit it
        'properties': {
            'type': {
                'type': 'string',
                # built-in types match the enum; 3rd-party types match the
                # pattern and land in the permissive catch-all branch below
                'anyOf': [
                    {'enum': types},
                    {'pattern': _THIRD_PARTY_TYPE_PATTERN},
                ],
            },
            'ttl': {'type': 'integer', 'minimum': 0},
            'octodns': {'$ref': '#/$defs/octodns_meta'},
        },
        # reject typos and unknown top-level keys. `unevaluatedProperties`
        # (unlike `additionalProperties`) sees through the if/then branches
        # below, so value/values/dynamic/geo still pass when the matching
        # branch declares them.
        'unevaluatedProperties': False,
        'allOf': [
            _type_branch(t, c)
            for t, c in sorted(Record.registered_types().items())
        ]
        + [_third_party_branch()],
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
        'propertyNames': _NAME_SCHEMA,
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
