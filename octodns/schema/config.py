#
#
#

'''
Build a JSON Schema describing the octoDNS main configuration file.

The schema covers all top-level sections of config.yaml: manager, providers,
processors, validators, secret_handlers, and zones. Built-in core classes get
tight property schemas; unknown (third-party) classes are allowed through
with any kwargs as long as `class` is present.

This schema is intended for external consumers (IDEs, CI lint). octoDNS's own
validation is unchanged.
'''

_STRING_ARRAY = {'type': 'array', 'items': {'type': 'string'}}
_STRING_LIST = {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1}
_INT_GTE0 = {'type': 'integer', 'minimum': 0}
_INT_GTE1 = {'type': 'integer', 'minimum': 1}


def _class_branch(dotted_class, then_props, required_props=None):
    '''Build an if/then branch keyed on a specific class value.'''
    then = {'properties': then_props}
    if required_props:
        then['required'] = required_props
    return {
        'if': {
            'properties': {'class': {'const': dotted_class}},
            'required': ['class'],
        },
        'then': then,
    }


def _pluggable_entry(class_branches, extra_props=None):
    '''
    Schema for a single pluggable entry (any provider/processor/etc. dict).

    `class` is required. Known classes get type-checked kwargs via if/then
    branches; unknown classes pass freely (additionalProperties: true).
    '''
    props = {'class': {'type': 'string'}}
    if extra_props:
        props.update(extra_props)
    return {
        'type': 'object',
        'required': ['class'],
        'properties': props,
        'additionalProperties': True,
        'allOf': class_branches,
    }


# ── Providers / Sources ───────────────────────────────────────────────────────

_PROVIDER_BRANCHES = [
    _class_branch(
        'octodns.provider.yaml.YamlProvider',
        {
            'directory': {'type': 'string'},
            'default_ttl': _INT_GTE0,
            'enforce_order': {'type': 'boolean'},
            'order_mode': {'type': 'string', 'enum': ['simple', 'natural']},
            'populate_should_replace': {'type': 'boolean'},
            'supports_root_ns': {'type': 'boolean'},
            'split_extension': {
                'oneOf': [{'type': 'string'}, {'type': 'boolean'}]
            },
            'split_catchall': {'type': 'boolean'},
            'shared_filename': {
                'oneOf': [{'type': 'string'}, {'type': 'boolean'}]
            },
            'disable_zonefile': {'type': 'boolean'},
            'escaped_semicolons': {'type': 'boolean'},
            'ignore_missing_zones': {'type': 'boolean'},
        },
        required_props=['directory'],
    ),
    _class_branch(
        'octodns.source.envvar.EnvVarSource',
        {
            'variable': {'type': 'string'},
            'name': {'type': 'string'},
            'ttl': _INT_GTE0,
        },
        required_props=['variable', 'name'],
    ),
    _class_branch(
        'octodns.source.tinydns.TinyDnsFileSource',
        {'directory': {'type': 'string'}, 'default_ttl': _INT_GTE0},
        required_props=['directory'],
    ),
]

# ── Processors ────────────────────────────────────────────────────────────────

_INCLUDE_TARGET = {'include_target': {'type': 'boolean'}}
_ALLOWLIST_PROPS = {'allowlist': _STRING_LIST, **_INCLUDE_TARGET}
_REJECTLIST_PROPS = {'rejectlist': _STRING_LIST, **_INCLUDE_TARGET}
_NETWORK_LIST = {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1}

_PROCESSOR_BRANCHES = [
    _class_branch('octodns.processor.acme.AcmeManagingProcessor', {}),
    _class_branch(
        'octodns.processor.arpa.AutoArpa',
        {
            'ttl': _INT_GTE0,
            'populate_should_replace': {'type': 'boolean'},
            'max_auto_arpa': _INT_GTE0,
            'inherit_ttl': {'type': 'boolean'},
            'wildcard_replacement': {'type': ['string', 'null']},
        },
    ),
    _class_branch(
        'octodns.processor.clamp.TtlClampProcessor',
        {'min_ttl': _INT_GTE0, 'max_ttl': _INT_GTE0},
    ),
    _class_branch(
        'octodns.processor.filter.TypeAllowlistFilter',
        _ALLOWLIST_PROPS,
        required_props=['allowlist'],
    ),
    _class_branch(
        'octodns.processor.filter.TypeRejectlistFilter',
        _REJECTLIST_PROPS,
        required_props=['rejectlist'],
    ),
    _class_branch(
        'octodns.processor.filter.NameAllowlistFilter',
        _ALLOWLIST_PROPS,
        required_props=['allowlist'],
    ),
    _class_branch(
        'octodns.processor.filter.NameRejectlistFilter',
        _REJECTLIST_PROPS,
        required_props=['rejectlist'],
    ),
    _class_branch(
        'octodns.processor.filter.ValueAllowlistFilter',
        _ALLOWLIST_PROPS,
        required_props=['allowlist'],
    ),
    _class_branch(
        'octodns.processor.filter.ValueRejectlistFilter',
        _REJECTLIST_PROPS,
        required_props=['rejectlist'],
    ),
    _class_branch(
        'octodns.processor.filter.NetworkValueAllowlistFilter',
        {'allowlist': _NETWORK_LIST},
        required_props=['allowlist'],
    ),
    _class_branch(
        'octodns.processor.filter.NetworkValueRejectlistFilter',
        {'rejectlist': _NETWORK_LIST},
        required_props=['rejectlist'],
    ),
    _class_branch('octodns.processor.filter.IgnoreRootNsFilter', {}),
    _class_branch(
        'octodns.processor.filter.ExcludeRootNsChanges',
        {'error': {'type': 'boolean'}},
    ),
    _class_branch(
        'octodns.processor.filter.ZoneNameFilter',
        {'error': {'type': 'boolean'}, **_INCLUDE_TARGET},
    ),
    _class_branch(
        'octodns.processor.meta.MetaProcessor',
        {
            'record_name': {'type': 'string'},
            'include_time': {'type': 'boolean'},
            'include_uuid': {'type': 'boolean'},
            'include_version': {'type': 'boolean'},
            'include_provider': {'type': 'boolean'},
            'include_extra': {
                'oneOf': [
                    {'type': 'object', 'additionalProperties': True},
                    {'type': 'null'},
                ]
            },
            'ttl': _INT_GTE0,
        },
    ),
    _class_branch(
        'octodns.processor.ownership.OwnershipProcessor',
        {
            'txt_name': {'type': 'string'},
            'txt_value': {'type': 'string'},
            'txt_ttl': _INT_GTE0,
            'should_replace': {'type': 'boolean'},
        },
    ),
    _class_branch(
        'octodns.processor.restrict.TtlRestrictionFilter',
        {
            'min_ttl': _INT_GTE0,
            'max_ttl': _INT_GTE0,
            'allowed_ttls': {
                'type': 'array',
                'items': _INT_GTE0,
                'minItems': 1,
            },
        },
    ),
    _class_branch('octodns.processor.spf.SpfDnsLookupProcessor', {}),
    _class_branch(
        'octodns.processor.templating.Templating',
        {
            'trailing_dots': {'type': 'boolean'},
            'context': {'type': 'object', 'additionalProperties': True},
        },
    ),
    _class_branch('octodns.processor.trailing_dots.EnsureTrailingDots', {}),
]

# ── Secret handlers ───────────────────────────────────────────────────────────

_SECRET_HANDLER_BRANCHES = [
    _class_branch('octodns.secret.environ.EnvironSecrets', {})
]

# ── Plan outputs ──────────────────────────────────────────────────────────────

_OUTPUT_FILENAME = {
    'output_filename': {'oneOf': [{'type': 'string'}, {'type': 'null'}]}
}

_PLAN_OUTPUT_BRANCHES = [
    _class_branch(
        'octodns.provider.plan.PlanLogger',
        {
            'level': {
                'type': 'string',
                'enum': ['debug', 'info', 'warn', 'warning', 'error'],
            }
        },
    ),
    _class_branch(
        'octodns.provider.plan.PlanJson',
        {
            'indent': {'oneOf': [_INT_GTE0, {'type': 'null'}]},
            'sort_keys': {'type': 'boolean'},
            **_OUTPUT_FILENAME,
        },
    ),
    _class_branch('octodns.provider.plan.PlanMarkdown', _OUTPUT_FILENAME),
    _class_branch('octodns.provider.plan.PlanHtml', _OUTPUT_FILENAME),
]

# ── Schema defs ───────────────────────────────────────────────────────────────

_TYPE_TO_NAMES_MAP = {
    'type': 'object',
    'additionalProperties': {'type': 'array', 'items': {'type': 'string'}},
}

_AUTO_ARPA_KWARGS = {
    'type': 'object',
    'additionalProperties': False,
    'properties': {
        'ttl': _INT_GTE0,
        'populate_should_replace': {'type': 'boolean'},
        'max_auto_arpa': _INT_GTE0,
        'inherit_ttl': {'type': 'boolean'},
        'wildcard_replacement': {'type': ['string', 'null']},
    },
}


def _manager_def():
    return {
        'type': 'object',
        'additionalProperties': False,
        'properties': {
            'max_workers': _INT_GTE1,
            'include_meta': {'type': 'boolean'},
            'enable_checksum': {'type': 'boolean'},
            'auto_arpa': {'oneOf': [{'type': 'boolean'}, _AUTO_ARPA_KWARGS]},
            'processors': _STRING_ARRAY,
            'post_processors': _STRING_ARRAY,
            'validators': {
                'type': 'object',
                'additionalProperties': False,
                'properties': {
                    'enabled': _STRING_ARRAY,
                    'record': {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            'validators': _TYPE_TO_NAMES_MAP,
                            'disable_validators': _TYPE_TO_NAMES_MAP,
                        },
                    },
                    'zone': {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            'validators': _STRING_ARRAY,
                            'disable_validators': _STRING_ARRAY,
                        },
                    },
                    # Deprecated aliases kept for backwards compatibility
                    'validators': _TYPE_TO_NAMES_MAP,
                    'disable_validators': _TYPE_TO_NAMES_MAP,
                },
            },
            'plan_outputs': {
                'type': 'object',
                'additionalProperties': {
                    '$ref': '#/$defs/pluggable_plan_output'
                },
            },
        },
    }


def _zone_def():
    return {
        'oneOf': [
            {
                'type': 'object',
                'required': ['alias'],
                'properties': {'alias': {'type': 'string'}},
                'additionalProperties': False,
            },
            {
                'type': 'object',
                'required': ['sources', 'targets'],
                'properties': {
                    'sources': _STRING_ARRAY,
                    'targets': _STRING_ARRAY,
                    'processors': _STRING_ARRAY,
                    'lenient': {'type': 'boolean'},
                    'glob': {'type': 'string'},
                    'regex': {'type': 'string'},
                },
                'additionalProperties': False,
            },
        ]
    }


def build_config_schema():
    '''Return a dict describing the JSON Schema for an octoDNS config file.'''
    return {
        '$schema': 'https://json-schema.org/draft/2020-12/schema',
        'title': 'octoDNS config file',
        'description': (
            'Schema for an octoDNS main configuration YAML file: '
            'providers, processors, validators, secret_handlers, and zones.'
        ),
        'type': 'object',
        'required': ['providers', 'zones'],
        'additionalProperties': False,
        'properties': {
            'manager': {'$ref': '#/$defs/manager'},
            'providers': {'$ref': '#/$defs/pluggable_map_provider'},
            'processors': {'$ref': '#/$defs/pluggable_map_processor'},
            'validators': {'$ref': '#/$defs/pluggable_map_validator'},
            'secret_handlers': {'$ref': '#/$defs/pluggable_map_secret_handler'},
            'zones': {'$ref': '#/$defs/zones'},
        },
        '$defs': {
            'manager': _manager_def(),
            'pluggable_map_provider': {
                'type': 'object',
                'additionalProperties': {'$ref': '#/$defs/pluggable_provider'},
            },
            'pluggable_map_processor': {
                'type': 'object',
                'additionalProperties': {'$ref': '#/$defs/pluggable_processor'},
            },
            'pluggable_map_validator': {
                'type': 'object',
                'additionalProperties': {'$ref': '#/$defs/pluggable_validator'},
            },
            'pluggable_map_secret_handler': {
                'type': 'object',
                'additionalProperties': {
                    '$ref': '#/$defs/pluggable_secret_handler'
                },
            },
            'pluggable_provider': _pluggable_entry(_PROVIDER_BRANCHES),
            'pluggable_processor': _pluggable_entry(
                _PROCESSOR_BRANCHES,
                # lenient is accepted by all processors via BaseProcessor
                extra_props={'lenient': {'type': 'boolean'}},
            ),
            'pluggable_validator': {
                'type': 'object',
                'required': ['class'],
                'properties': {
                    'class': {'type': 'string'},
                    # types is popped by manager before passing kwargs to ctor
                    'types': {'oneOf': [{'type': 'string'}, _STRING_ARRAY]},
                },
                'additionalProperties': True,
            },
            'pluggable_secret_handler': _pluggable_entry(
                _SECRET_HANDLER_BRANCHES
            ),
            'pluggable_plan_output': _pluggable_entry(_PLAN_OUTPUT_BRANCHES),
            'zones': {
                'type': 'object',
                'additionalProperties': {'$ref': '#/$defs/zone'},
            },
            'zone': _zone_def(),
        },
    }
