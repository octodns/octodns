#
#
#

import json
from io import StringIO
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import jsonschema

from octodns.cmds.schema import main as schema_main
from octodns.schema import build_config_schema
from octodns.yaml import safe_load


class TestConfigSchema(TestCase):
    def _validator(self):
        return jsonschema.Draft202012Validator(
            build_config_schema(),
            format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER,
        )

    def _valid(self, data):
        errors = list(self._validator().iter_errors(data))
        self.assertEqual([], errors, f'unexpected errors: {errors}')

    def _invalid(self, data):
        with self.assertRaises(jsonschema.ValidationError):
            self._validator().validate(data)

    def _base(self, **extra):
        d = {'providers': {}, 'zones': {}}
        d.update(extra)
        return d

    def test_schema_is_valid_json_schema(self):
        jsonschema.Draft202012Validator.check_schema(build_config_schema())

    # ── Top-level structure ───────────────────────────────────────────────────

    def test_providers_and_zones_required(self):
        self._invalid({})
        self._invalid({'providers': {}})
        self._invalid({'zones': {}})
        self._valid({'providers': {}, 'zones': {}})

    def test_unknown_top_level_key_rejected(self):
        self._invalid(self._base(provders={}))

    def test_all_optional_top_level_keys_valid(self):
        self._valid(
            self._base(
                manager={}, processors={}, validators={}, secret_handlers={}
            )
        )

    # ── manager: ─────────────────────────────────────────────────────────────

    def test_unknown_manager_key_rejected(self):
        self._invalid(self._base(manager={'max_workerss': 2}))

    def test_valid_manager_config(self):
        self._valid(
            self._base(
                manager={
                    'max_workers': 4,
                    'include_meta': True,
                    'enable_checksum': True,
                    'auto_arpa': True,
                    'processors': ['p1'],
                    'post_processors': ['p2'],
                    'validators': {
                        'enabled': ['legacy'],
                        'record': {
                            'validators': {'A': ['v1'], '*': ['v2']},
                            'disable_validators': {'AAAA': ['bad-v']},
                        },
                        'zone': {
                            'validators': ['my-zone-v'],
                            'disable_validators': ['other-zone-v'],
                        },
                    },
                    'plan_outputs': {
                        'logs': {
                            'class': 'octodns.provider.plan.PlanLogger',
                            'level': 'debug',
                        }
                    },
                }
            )
        )

    def test_auto_arpa_as_boolean(self):
        self._valid(self._base(manager={'auto_arpa': True}))
        self._valid(self._base(manager={'auto_arpa': False}))

    def test_auto_arpa_as_dict(self):
        self._valid(
            self._base(
                manager={
                    'auto_arpa': {
                        'ttl': 1800,
                        'populate_should_replace': True,
                        'max_auto_arpa': 100,
                        'inherit_ttl': False,
                        'wildcard_replacement': 'wildcard',
                    }
                }
            )
        )

    def test_auto_arpa_dict_unknown_key_rejected(self):
        self._invalid(
            self._base(manager={'auto_arpa': {'unknown_kwarg': True}})
        )

    def test_validators_unknown_key_rejected(self):
        self._invalid(
            self._base(manager={'validators': {'typo_enabled': ['legacy']}})
        )

    def test_validators_record_unknown_key_rejected(self):
        self._invalid(
            self._base(
                manager={
                    'validators': {'record': {'typo_validators': {'*': ['v']}}}
                }
            )
        )

    def test_validators_zone_unknown_key_rejected(self):
        self._invalid(
            self._base(
                manager={'validators': {'zone': {'typo_validators': ['my-v']}}}
            )
        )

    def test_plan_outputs_logger_bad_level_rejected(self):
        self._invalid(
            self._base(
                manager={
                    'plan_outputs': {
                        'logs': {
                            'class': 'octodns.provider.plan.PlanLogger',
                            'level': 'verbose',
                        }
                    }
                }
            )
        )

    def test_plan_outputs_json(self):
        self._valid(
            self._base(
                manager={
                    'plan_outputs': {
                        'j': {
                            'class': 'octodns.provider.plan.PlanJson',
                            'indent': 2,
                            'sort_keys': False,
                            'output_filename': '/tmp/plan.json',
                        }
                    }
                }
            )
        )

    def test_plan_outputs_markdown_and_html(self):
        self._valid(
            self._base(
                manager={
                    'plan_outputs': {
                        'md': {
                            'class': 'octodns.provider.plan.PlanMarkdown',
                            'output_filename': '/tmp/plan.md',
                        },
                        'html': {
                            'class': 'octodns.provider.plan.PlanHtml',
                            'output_filename': '/tmp/plan.html',
                        },
                    }
                }
            )
        )

    # ── providers: ───────────────────────────────────────────────────────────

    def test_provider_missing_class_fails(self):
        self._invalid(
            {'providers': {'config': {'directory': './zones'}}, 'zones': {}}
        )

    def test_yaml_provider_valid_minimal(self):
        self._valid(
            {
                'providers': {
                    'config': {
                        'class': 'octodns.provider.yaml.YamlProvider',
                        'directory': './zones',
                    }
                },
                'zones': {},
            }
        )

    def test_yaml_provider_missing_directory_fails(self):
        self._invalid(
            {
                'providers': {
                    'config': {'class': 'octodns.provider.yaml.YamlProvider'}
                },
                'zones': {},
            }
        )

    def test_yaml_provider_all_kwargs_valid(self):
        self._valid(
            {
                'providers': {
                    'config': {
                        'class': 'octodns.provider.yaml.YamlProvider',
                        'directory': './zones',
                        'default_ttl': 3600,
                        'enforce_order': True,
                        'order_mode': 'natural',
                        'populate_should_replace': False,
                        'supports_root_ns': True,
                        'split_extension': '.',
                        'split_catchall': True,
                        'shared_filename': False,
                        'disable_zonefile': False,
                        'escaped_semicolons': True,
                        'ignore_missing_zones': False,
                    }
                },
                'zones': {},
            }
        )

    def test_yaml_provider_bad_order_mode_fails(self):
        self._invalid(
            {
                'providers': {
                    'config': {
                        'class': 'octodns.provider.yaml.YamlProvider',
                        'directory': './zones',
                        'order_mode': 'random',
                    }
                },
                'zones': {},
            }
        )

    def test_env_var_source_valid(self):
        self._valid(
            {
                'providers': {
                    'ver': {
                        'class': 'octodns.source.envvar.EnvVarSource',
                        'variable': 'VERSION',
                        'name': 'deploy-version',
                        'ttl': 60,
                    }
                },
                'zones': {},
            }
        )

    def test_env_var_source_missing_name_fails(self):
        self._invalid(
            {
                'providers': {
                    'ver': {
                        'class': 'octodns.source.envvar.EnvVarSource',
                        'variable': 'VERSION',
                    }
                },
                'zones': {},
            }
        )

    def test_tiny_dns_file_source_valid(self):
        self._valid(
            {
                'providers': {
                    'tiny': {
                        'class': 'octodns.source.tinydns.TinyDnsFileSource',
                        'directory': './zones',
                        'default_ttl': 3600,
                    }
                },
                'zones': {},
            }
        )

    def test_unknown_provider_class_allowed_with_any_kwargs(self):
        self._valid(
            {
                'providers': {
                    'route53': {
                        'class': 'octodns_route53.Route53Provider',
                        'access_key_id': 'env/AWS_ACCESS_KEY_ID',
                        'secret_access_key': 'env/AWS_SECRET_ACCESS_KEY',
                        'any_kwarg': 'is_ok',
                    }
                },
                'zones': {},
            }
        )

    # ── processors: ──────────────────────────────────────────────────────────

    def test_processor_missing_class_fails(self):
        self._invalid(self._base(processors={'p': {'lenient': True}}))

    def test_processor_lenient_common_kwarg(self):
        self._valid(
            self._base(
                processors={
                    'p': {
                        'class': 'octodns.processor.acme.AcmeManagingProcessor',
                        'lenient': True,
                    }
                }
            )
        )

    def test_processors_with_no_kwargs(self):
        for class_ in [
            'octodns.processor.acme.AcmeManagingProcessor',
            'octodns.processor.filter.IgnoreRootNsFilter',
            'octodns.processor.spf.SpfDnsLookupProcessor',
            'octodns.processor.trailing_dots.EnsureTrailingDots',
        ]:
            self._valid(self._base(processors={'p': {'class': class_}}))

    def test_type_allowlist_filter_valid(self):
        self._valid(
            self._base(
                processors={
                    'f': {
                        'class': 'octodns.processor.filter.TypeAllowlistFilter',
                        'allowlist': ['A', 'AAAA'],
                        'include_target': True,
                    }
                }
            )
        )

    def test_type_allowlist_filter_missing_allowlist_fails(self):
        self._invalid(
            self._base(
                processors={
                    'f': {
                        'class': 'octodns.processor.filter.TypeAllowlistFilter'
                    }
                }
            )
        )

    def test_type_rejectlist_filter_valid(self):
        self._valid(
            self._base(
                processors={
                    'f': {
                        'class': 'octodns.processor.filter.TypeRejectlistFilter',
                        'rejectlist': ['CNAME'],
                    }
                }
            )
        )

    def test_name_filter_valid(self):
        self._valid(
            self._base(
                processors={
                    'allow': {
                        'class': 'octodns.processor.filter.NameAllowlistFilter',
                        'allowlist': ['www', '/sub-.*$/'],
                    },
                    'reject': {
                        'class': 'octodns.processor.filter.NameRejectlistFilter',
                        'rejectlist': ['internal'],
                    },
                }
            )
        )

    def test_value_filter_valid(self):
        self._valid(
            self._base(
                processors={
                    'allow': {
                        'class': 'octodns.processor.filter.ValueAllowlistFilter',
                        'allowlist': ['1.2.3.4'],
                    },
                    'reject': {
                        'class': 'octodns.processor.filter.ValueRejectlistFilter',
                        'rejectlist': ['/10\\.0\\..*/'],
                    },
                }
            )
        )

    def test_network_filter_valid(self):
        self._valid(
            self._base(
                processors={
                    'allow': {
                        'class': 'octodns.processor.filter.NetworkValueAllowlistFilter',
                        'allowlist': ['10.0.0.0/8', '192.168.0.0/16'],
                    },
                    'reject': {
                        'class': 'octodns.processor.filter.NetworkValueRejectlistFilter',
                        'rejectlist': ['127.0.0.1/32'],
                    },
                }
            )
        )

    def test_exclude_root_ns_changes_valid(self):
        self._valid(
            self._base(
                processors={
                    'p': {
                        'class': 'octodns.processor.filter.ExcludeRootNsChanges',
                        'error': False,
                    }
                }
            )
        )

    def test_zone_name_filter_valid(self):
        self._valid(
            self._base(
                processors={
                    'p': {
                        'class': 'octodns.processor.filter.ZoneNameFilter',
                        'error': True,
                        'include_target': False,
                    }
                }
            )
        )

    def test_meta_processor_valid(self):
        self._valid(
            self._base(
                processors={
                    'meta': {
                        'class': 'octodns.processor.meta.MetaProcessor',
                        'record_name': 'meta',
                        'include_time': True,
                        'include_uuid': True,
                        'include_version': True,
                        'include_provider': False,
                        'include_extra': {'key': 'val'},
                        'ttl': 60,
                    }
                }
            )
        )

    def test_ownership_processor_valid(self):
        self._valid(
            self._base(
                processors={
                    'owner': {
                        'class': 'octodns.processor.ownership.OwnershipProcessor',
                        'txt_name': '_owner',
                        'txt_value': '*octodns*',
                        'txt_ttl': 60,
                        'should_replace': False,
                    }
                }
            )
        )

    def test_ttl_restriction_filter_valid(self):
        self._valid(
            self._base(
                processors={
                    'ttl': {
                        'class': 'octodns.processor.restrict.TtlRestrictionFilter',
                        'min_ttl': 60,
                        'max_ttl': 3600,
                        'allowed_ttls': [300, 900, 3600],
                    }
                }
            )
        )

    def test_clamp_processor_valid(self):
        self._valid(
            self._base(
                processors={
                    'clamp': {
                        'class': 'octodns.processor.clamp.TtlClampProcessor',
                        'min_ttl': 300,
                        'max_ttl': 86400,
                    }
                }
            )
        )

    def test_arpa_processor_valid(self):
        self._valid(
            self._base(
                processors={
                    'arpa': {
                        'class': 'octodns.processor.arpa.AutoArpa',
                        'ttl': 3600,
                        'populate_should_replace': False,
                        'max_auto_arpa': 999,
                        'inherit_ttl': True,
                        'wildcard_replacement': None,
                    }
                }
            )
        )

    def test_templating_processor_valid(self):
        self._valid(
            self._base(
                processors={
                    'tmpl': {
                        'class': 'octodns.processor.templating.Templating',
                        'trailing_dots': True,
                        'context': {'key': 'value', 'num': 42},
                    }
                }
            )
        )

    def test_unknown_processor_class_allowed_with_any_kwargs(self):
        self._valid(
            self._base(
                processors={
                    'custom': {
                        'class': 'my.custom.Processor',
                        'arbitrary': 'kwarg',
                        'nested': {'ok': True},
                    }
                }
            )
        )

    # ── validators: ──────────────────────────────────────────────────────────

    def test_validator_missing_class_fails(self):
        self._invalid(self._base(validators={'v': {'types': ['A']}}))

    def test_validator_types_as_list(self):
        self._valid(
            self._base(
                validators={
                    'my-v': {'class': 'my.Validator', 'types': ['A', 'AAAA']}
                }
            )
        )

    def test_validator_types_as_string(self):
        self._valid(
            self._base(
                validators={'my-v': {'class': 'my.Validator', 'types': 'MX'}}
            )
        )

    def test_validator_no_types(self):
        self._valid(self._base(validators={'my-v': {'class': 'my.Validator'}}))

    def test_validator_with_kwargs(self):
        self._valid(
            self._base(
                validators={
                    'my-v': {
                        'class': 'my.Validator',
                        'types': ['A'],
                        'custom_kwarg': 'value',
                    }
                }
            )
        )

    # ── secret_handlers: ─────────────────────────────────────────────────────

    def test_secret_handler_missing_class_fails(self):
        self._invalid(self._base(secret_handlers={'sh': {'key': 'val'}}))

    def test_environ_secrets_valid(self):
        self._valid(
            self._base(
                secret_handlers={
                    'env': {'class': 'octodns.secret.environ.EnvironSecrets'}
                }
            )
        )

    def test_unknown_secret_handler_allowed(self):
        self._valid(
            self._base(
                secret_handlers={
                    'vault': {
                        'class': 'my.VaultSecrets',
                        'url': 'https://vault.example.com',
                    }
                }
            )
        )

    # ── zones: ───────────────────────────────────────────────────────────────

    def test_regular_zone_valid(self):
        self._valid(
            {
                'providers': {},
                'zones': {
                    'example.com.': {
                        'sources': ['config'],
                        'targets': ['route53'],
                    }
                },
            }
        )

    def test_alias_zone_valid(self):
        self._valid(
            {
                'providers': {},
                'zones': {
                    'example.com.': {
                        'sources': ['config'],
                        'targets': ['route53'],
                    },
                    'alias.example.com.': {'alias': 'example.com.'},
                },
            }
        )

    def test_zone_with_all_optional_fields(self):
        self._valid(
            {
                'providers': {},
                'zones': {
                    'example.com.': {
                        'sources': ['config'],
                        'targets': ['route53'],
                        'processors': ['p1'],
                        'lenient': True,
                        'glob': '*.example.*',
                    },
                    '*.arpa.': {
                        'sources': ['config'],
                        'targets': ['route53'],
                        'regex': r'^.*\.arpa\.$',
                    },
                },
            }
        )

    def test_zone_missing_targets_fails(self):
        self._invalid(
            {
                'providers': {},
                'zones': {'example.com.': {'sources': ['config']}},
            }
        )

    def test_zone_missing_sources_fails(self):
        self._invalid(
            {
                'providers': {},
                'zones': {'example.com.': {'targets': ['route53']}},
            }
        )

    def test_zone_empty_dict_fails(self):
        self._invalid({'providers': {}, 'zones': {'example.com.': {}}})

    def test_zone_unknown_key_rejected(self):
        self._invalid(
            {
                'providers': {},
                'zones': {
                    'example.com.': {
                        'sources': ['config'],
                        'targets': ['route53'],
                        'unknownkey': True,
                    }
                },
            }
        )

    def test_alias_zone_with_extra_key_rejected(self):
        self._invalid(
            {
                'providers': {},
                'zones': {
                    'alias.example.com.': {
                        'alias': 'example.com.',
                        'sources': ['config'],
                    }
                },
            }
        )

    # ── Round-trip ────────────────────────────────────────────────────────────

    def test_round_trip_config_fixtures(self):
        v = self._validator()
        for path in (
            'tests/config/simple.yaml',
            'tests/config/simple-alias-zone.yaml',
            'tests/config/dynamic-arpa.yaml',
            'tests/config/validators-add.yaml',
        ):
            with open(path) as fh:
                data = safe_load(fh.read(), enforce_order=False)
            errors = list(v.iter_errors(data))
            self.assertEqual(
                [], errors, f'{path} failed schema validation: {errors}'
            )

    # ── CLI ───────────────────────────────────────────────────────────────────

    def test_cmd_schema_kind_config_stdout(self):
        buf = StringIO()
        with patch('sys.argv', ['octodns-schema', '--kind', 'config']), patch(
            'sys.stdout', buf
        ):
            schema_main()
        schema = json.loads(buf.getvalue())
        jsonschema.Draft202012Validator.check_schema(schema)

    def test_cmd_schema_kind_config_output_file(self):
        with TemporaryDirectory() as tmp:
            path = f'{tmp}/config.schema.json'
            with patch(
                'sys.argv',
                ['octodns-schema', '--kind', 'config', '--output', path],
            ):
                schema_main()
            with open(path) as fh:
                schema = json.load(fh)
            jsonschema.Draft202012Validator.check_schema(schema)
