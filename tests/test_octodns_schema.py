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
from octodns.record import Record
from octodns.record.base import ValuesMixin
from octodns.schema import build_zone_schema
from octodns.yaml import safe_load


class TestSchema(TestCase):
    def test_schema_is_valid_json_schema(self):
        schema = build_zone_schema()
        jsonschema.Draft202012Validator.check_schema(schema)

    def test_every_registered_type_is_in_enum(self):
        schema = build_zone_schema()
        enum = set(schema['$defs']['record']['properties']['type']['enum'])
        registered = set(Record.registered_types().keys())
        self.assertEqual(registered, enum)

    def test_every_registered_type_has_exactly_one_branch(self):
        schema = build_zone_schema()
        branches = schema['$defs']['record']['allOf']
        types_in_branches = [
            b['if']['properties']['type']['const'] for b in branches
        ]
        # no duplicates
        self.assertEqual(len(types_in_branches), len(set(types_in_branches)))
        # covers everything
        self.assertEqual(
            set(Record.registered_types().keys()), set(types_in_branches)
        )

    def _validator(self):
        return jsonschema.Draft202012Validator(
            build_zone_schema(),
            format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER,
        )

    def test_valid_a_record_with_single_value(self):
        self._validator().validate(
            {'www': {'type': 'A', 'ttl': 300, 'value': '1.2.3.4'}}
        )

    def test_valid_a_record_with_values_list(self):
        self._validator().validate(
            {'www': {'type': 'A', 'ttl': 300, 'values': ['1.2.3.4', '2.3.4.5']}}
        )

    def test_valid_aaaa_record(self):
        self._validator().validate(
            {
                'aaaa': {
                    'type': 'AAAA',
                    'ttl': 600,
                    'value': '2601:644:500:e210:62f8:1dff:feb8:947a',
                }
            }
        )

    def test_valid_cname_record(self):
        self._validator().validate(
            {'cname': {'type': 'CNAME', 'ttl': 300, 'value': 'unit.tests.'}}
        )

    def test_valid_txt_record(self):
        self._validator().validate(
            {
                'txt': {
                    'type': 'TXT',
                    'ttl': 600,
                    'values': ['one', 'two', 'three'],
                }
            }
        )

    def test_valid_multiple_records_at_same_name(self):
        self._validator().validate(
            {
                '': [
                    {'type': 'A', 'ttl': 300, 'values': ['1.2.3.4']},
                    {
                        'type': 'AAAA',
                        'ttl': 300,
                        'value': '2601:644:500:e210:62f8:1dff:feb8:947a',
                    },
                ]
            }
        )

    def test_valid_record_without_ttl(self):
        # YamlProvider fills in default_ttl; the schema shouldn't force ttl
        self._validator().validate(
            {'sub': {'type': 'CNAME', 'value': 'unit.tests.'}}
        )

    def test_valid_record_with_octodns_metadata(self):
        self._validator().validate(
            {
                'x': {
                    'type': 'A',
                    'ttl': 300,
                    'value': '1.2.3.4',
                    'octodns': {
                        'ignored': True,
                        'excluded': ['provider-a'],
                        'included': ['provider-b'],
                        'lenient': False,
                        'healthcheck': {
                            'protocol': 'HTTPS',
                            'host': 'example.com',
                            'path': '/_ready',
                            'port': 8080,
                        },
                    },
                }
            }
        )

    def test_invalid_unknown_type_rejected(self):
        with self.assertRaises(jsonschema.ValidationError):
            self._validator().validate(
                {'www': {'type': 'NOPE', 'ttl': 300, 'value': '1.2.3.4'}}
            )

    def test_invalid_missing_type_rejected(self):
        with self.assertRaises(jsonschema.ValidationError):
            self._validator().validate(
                {'www': {'ttl': 300, 'value': '1.2.3.4'}}
            )

    def test_invalid_ipv4_rejected(self):
        with self.assertRaises(jsonschema.ValidationError):
            self._validator().validate(
                {'www': {'type': 'A', 'ttl': 300, 'value': 'not-an-ip'}}
            )

    def test_invalid_ipv6_in_a_record_rejected(self):
        with self.assertRaises(jsonschema.ValidationError):
            self._validator().validate(
                {'www': {'type': 'A', 'ttl': 300, 'value': '::1'}}
            )

    def test_invalid_ttl_negative_rejected(self):
        with self.assertRaises(jsonschema.ValidationError):
            self._validator().validate(
                {'www': {'type': 'A', 'ttl': -1, 'value': '1.2.3.4'}}
            )

    def test_invalid_healthcheck_protocol_rejected(self):
        with self.assertRaises(jsonschema.ValidationError):
            self._validator().validate(
                {
                    'www': {
                        'type': 'A',
                        'ttl': 300,
                        'value': '1.2.3.4',
                        'octodns': {'healthcheck': {'protocol': 'FOO'}},
                    }
                }
            )

    def test_valid_alias_record(self):
        self._validator().validate(
            {'': {'type': 'ALIAS', 'ttl': 300, 'value': 'unit.tests.'}}
        )

    def test_valid_dname_record(self):
        self._validator().validate(
            {'dname': {'type': 'DNAME', 'ttl': 300, 'value': 'unit.tests.'}}
        )

    def test_valid_ns_record(self):
        self._validator().validate(
            {
                'sub': {
                    'type': 'NS',
                    'ttl': 3600,
                    'values': ['ns1.example.com.', 'ns2.example.com.'],
                }
            }
        )

    def test_valid_ptr_record(self):
        self._validator().validate(
            {'ptr': {'type': 'PTR', 'ttl': 300, 'values': ['foo.bar.com.']}}
        )

    def test_valid_spf_record(self):
        self._validator().validate(
            {
                'spf': {
                    'type': 'SPF',
                    'ttl': 600,
                    'value': 'v=spf1 ip4:192.168.0.1/16-all',
                }
            }
        )

    def test_valid_mx_record_modern(self):
        self._validator().validate(
            {
                'mx': {
                    'type': 'MX',
                    'ttl': 300,
                    'values': [
                        {'preference': 10, 'exchange': 'mx.example.com.'}
                    ],
                }
            }
        )

    def test_valid_mx_record_legacy_priority_value(self):
        # legacy aliases supported by MxValue
        self._validator().validate(
            {
                'mx': {
                    'type': 'MX',
                    'ttl': 300,
                    'values': [{'priority': 10, 'value': 'mx.example.com.'}],
                }
            }
        )

    def test_invalid_mx_missing_preference_rejected(self):
        with self.assertRaises(jsonschema.ValidationError):
            self._validator().validate(
                {
                    'mx': {
                        'type': 'MX',
                        'ttl': 300,
                        'values': [{'exchange': 'mx.example.com.'}],
                    }
                }
            )

    def test_valid_srv_record(self):
        self._validator().validate(
            {
                '_srv._tcp': {
                    'type': 'SRV',
                    'ttl': 600,
                    'values': [
                        {
                            'priority': 10,
                            'weight': 20,
                            'port': 30,
                            'target': 'foo.example.com.',
                        }
                    ],
                }
            }
        )

    def test_invalid_srv_missing_port_rejected(self):
        with self.assertRaises(jsonschema.ValidationError):
            self._validator().validate(
                {
                    '_srv._tcp': {
                        'type': 'SRV',
                        'ttl': 600,
                        'values': [
                            {
                                'priority': 10,
                                'weight': 20,
                                'target': 'foo.example.com.',
                            }
                        ],
                    }
                }
            )

    def test_valid_caa_record(self):
        self._validator().validate(
            {
                'caa': {
                    'type': 'CAA',
                    'ttl': 3600,
                    'values': [
                        {'flags': 0, 'tag': 'issue', 'value': 'ca.example.com'}
                    ],
                }
            }
        )

    def test_invalid_caa_flags_out_of_range_rejected(self):
        with self.assertRaises(jsonschema.ValidationError):
            self._validator().validate(
                {
                    'caa': {
                        'type': 'CAA',
                        'ttl': 3600,
                        'values': [
                            {
                                'flags': 999,
                                'tag': 'issue',
                                'value': 'ca.example.com',
                            }
                        ],
                    }
                }
            )

    def test_valid_sshfp_record(self):
        self._validator().validate(
            {
                '': {
                    'type': 'SSHFP',
                    'ttl': 3600,
                    'values': [
                        {
                            'algorithm': 1,
                            'fingerprint_type': 1,
                            'fingerprint': (
                                'bf6b6825d2977c511a475bbefb88aad54a92ac73'
                            ),
                        }
                    ],
                }
            }
        )

    def test_invalid_sshfp_algorithm_rejected(self):
        with self.assertRaises(jsonschema.ValidationError):
            self._validator().validate(
                {
                    '': {
                        'type': 'SSHFP',
                        'ttl': 3600,
                        'values': [
                            {
                                'algorithm': 99,
                                'fingerprint_type': 1,
                                'fingerprint': 'abc',
                            }
                        ],
                    }
                }
            )

    def test_valid_tlsa_record(self):
        self._validator().validate(
            {
                '_443._tcp': {
                    'type': 'TLSA',
                    'ttl': 3600,
                    'values': [
                        {
                            'certificate_usage': 3,
                            'selector': 1,
                            'matching_type': 1,
                            'certificate_association_data': 'abc123',
                        }
                    ],
                }
            }
        )

    def test_invalid_tlsa_selector_out_of_range_rejected(self):
        with self.assertRaises(jsonschema.ValidationError):
            self._validator().validate(
                {
                    '_443._tcp': {
                        'type': 'TLSA',
                        'ttl': 3600,
                        'values': [
                            {
                                'certificate_usage': 3,
                                'selector': 99,
                                'matching_type': 1,
                                'certificate_association_data': 'abc123',
                            }
                        ],
                    }
                }
            )

    def test_valid_naptr_record(self):
        self._validator().validate(
            {
                'naptr': {
                    'type': 'NAPTR',
                    'ttl': 600,
                    'values': [
                        {
                            'order': 100,
                            'preference': 100,
                            'flags': 'U',
                            'service': 'SIP+D2U',
                            'regexp': ('!^.*$!sip:info@example.com!'),
                            'replacement': '.',
                        }
                    ],
                }
            }
        )

    def test_invalid_naptr_flags_rejected(self):
        with self.assertRaises(jsonschema.ValidationError):
            self._validator().validate(
                {
                    'naptr': {
                        'type': 'NAPTR',
                        'ttl': 600,
                        'values': [
                            {
                                'order': 100,
                                'preference': 100,
                                'flags': 'Z',
                                'service': 'SIP+D2U',
                                'regexp': '.',
                                'replacement': '.',
                            }
                        ],
                    }
                }
            )

    def test_valid_loc_record(self):
        self._validator().validate(
            {
                'loc': {
                    'type': 'LOC',
                    'ttl': 300,
                    'values': [
                        {
                            'lat_degrees': 31,
                            'lat_minutes': 58,
                            'lat_seconds': 52.1,
                            'lat_direction': 'S',
                            'long_degrees': 115,
                            'long_minutes': 49,
                            'long_seconds': 11.7,
                            'long_direction': 'E',
                            'altitude': 20,
                            'size': 10,
                            'precision_horz': 10,
                            'precision_vert': 2,
                        }
                    ],
                }
            }
        )

    def test_valid_ds_record_modern(self):
        self._validator().validate(
            {
                'ds': {
                    'type': 'DS',
                    'ttl': 3600,
                    'values': [
                        {
                            'key_tag': 60485,
                            'algorithm': 5,
                            'digest_type': 1,
                            'digest': (
                                '2BB183AF5F22588179A53B0A98631FAD1A292118'
                            ),
                        }
                    ],
                }
            }
        )

    def test_valid_dynamic_a_record(self):
        self._validator().validate(
            {
                'a': {
                    'type': 'A',
                    'ttl': 300,
                    'values': ['1.1.1.1'],
                    'dynamic': {
                        'pools': {
                            'iad': {
                                'values': [
                                    {'value': '2.2.2.2', 'weight': 1},
                                    {'value': '3.3.3.3', 'weight': 2},
                                ]
                            },
                            'sea': {
                                'fallback': 'iad',
                                'values': [
                                    {
                                        'value': '4.4.4.4',
                                        'weight': 1,
                                        'status': 'obey',
                                    }
                                ],
                            },
                        },
                        'rules': [
                            {'geos': ['NA-US-CA'], 'pool': 'sea'},
                            {'pool': 'iad'},
                        ],
                    },
                }
            }
        )

    def test_valid_dynamic_cname_record(self):
        self._validator().validate(
            {
                'cname': {
                    'type': 'CNAME',
                    'ttl': 300,
                    'value': 'fallback.example.com.',
                    'dynamic': {
                        'pools': {
                            'p1': {'values': [{'value': 'one.example.com.'}]}
                        },
                        'rules': [{'pool': 'p1'}],
                    },
                }
            }
        )

    def test_invalid_dynamic_pool_value_wrong_ip_version(self):
        with self.assertRaises(jsonschema.ValidationError):
            self._validator().validate(
                {
                    'a': {
                        'type': 'A',
                        'ttl': 300,
                        'values': ['1.1.1.1'],
                        'dynamic': {
                            'pools': {
                                'p': {
                                    # IPv6 in an A pool
                                    'values': [{'value': '::1'}]
                                }
                            },
                            'rules': [{'pool': 'p'}],
                        },
                    }
                }
            )

    def test_invalid_dynamic_weight_out_of_range(self):
        with self.assertRaises(jsonschema.ValidationError):
            self._validator().validate(
                {
                    'a': {
                        'type': 'A',
                        'ttl': 300,
                        'values': ['1.1.1.1'],
                        'dynamic': {
                            'pools': {
                                'p': {
                                    'values': [
                                        {'value': '1.1.1.1', 'weight': 500}
                                    ]
                                }
                            },
                            'rules': [{'pool': 'p'}],
                        },
                    }
                }
            )

    def test_invalid_dynamic_status_enum(self):
        with self.assertRaises(jsonschema.ValidationError):
            self._validator().validate(
                {
                    'a': {
                        'type': 'A',
                        'ttl': 300,
                        'values': ['1.1.1.1'],
                        'dynamic': {
                            'pools': {
                                'p': {
                                    'values': [
                                        {'value': '1.1.1.1', 'status': 'nope'}
                                    ]
                                }
                            },
                            'rules': [{'pool': 'p'}],
                        },
                    }
                }
            )

    def test_valid_geo_a_record(self):
        self._validator().validate(
            {
                '': {
                    'type': 'A',
                    'ttl': 300,
                    'values': ['1.2.3.4'],
                    'geo': {
                        'AF': ['2.2.3.4'],
                        'AS-JP': ['3.2.3.4'],
                        'NA-US-CA': ['5.2.3.4'],
                    },
                }
            }
        )

    def test_invalid_geo_code_pattern_rejected(self):
        with self.assertRaises(jsonschema.ValidationError):
            self._validator().validate(
                {
                    '': {
                        'type': 'A',
                        'ttl': 300,
                        'values': ['1.2.3.4'],
                        # lowercase continent code — invalid format
                        'geo': {'eu': ['2.2.3.4']},
                    }
                }
            )

    def test_valid_svcb_record(self):
        self._validator().validate(
            {
                '_svc': {
                    'type': 'SVCB',
                    'ttl': 300,
                    'values': [
                        {
                            'svcpriority': 1,
                            'targetname': 'svc.example.com.',
                            'svcparams': {'alpn': ['h2', 'h3'], 'port': 8443},
                        }
                    ],
                }
            }
        )

    def test_invalid_svcb_missing_targetname_rejected(self):
        with self.assertRaises(jsonschema.ValidationError):
            self._validator().validate(
                {
                    '_svc': {
                        'type': 'SVCB',
                        'ttl': 300,
                        'values': [{'svcpriority': 1}],
                    }
                }
            )

    def test_invalid_svcb_priority_out_of_range_rejected(self):
        with self.assertRaises(jsonschema.ValidationError):
            self._validator().validate(
                {
                    '_svc': {
                        'type': 'SVCB',
                        'ttl': 300,
                        'values': [
                            {
                                'svcpriority': 99999,
                                'targetname': 'svc.example.com.',
                            }
                        ],
                    }
                }
            )

    def test_valid_https_record(self):
        self._validator().validate(
            {
                'https': {
                    'type': 'HTTPS',
                    'ttl': 300,
                    'values': [
                        {
                            'svcpriority': 1,
                            'targetname': '.',
                            'svcparams': {'alpn': ['h2']},
                        }
                    ],
                }
            }
        )

    def test_valid_urlfwd_record(self):
        self._validator().validate(
            {
                'fwd': {
                    'type': 'URLFWD',
                    'ttl': 300,
                    'values': [
                        {
                            'path': '/',
                            'target': 'https://example.com/',
                            'code': 301,
                            'masking': 2,
                            'query': 0,
                        }
                    ],
                }
            }
        )

    def test_invalid_urlfwd_bad_code_rejected(self):
        with self.assertRaises(jsonschema.ValidationError):
            self._validator().validate(
                {
                    'fwd': {
                        'type': 'URLFWD',
                        'ttl': 300,
                        'values': [
                            {
                                'path': '/',
                                'target': 'https://example.com/',
                                'code': 404,
                                'masking': 2,
                                'query': 0,
                            }
                        ],
                    }
                }
            )

    def test_valid_openpgpkey_record(self):
        self._validator().validate(
            {
                'openpgpkey': {
                    'type': 'OPENPGPKEY',
                    'ttl': 3600,
                    'values': ['mQINBF...'],
                }
            }
        )

    def test_third_party_record_without_schema_falls_back_to_permissive(self):
        # external packages may register record types whose value classes
        # don't yet expose `_schema()`; the generated schema must still be
        # valid and accept those records with any value shape
        class _ThirdPartyValue(str):
            pass

        class _ThirdPartyRecord(ValuesMixin, Record):
            _type = 'XXTEST'
            _value_type = _ThirdPartyValue

        Record.register_type(_ThirdPartyRecord)
        try:
            schema = build_zone_schema()
            jsonschema.Draft202012Validator.check_schema(schema)
            self.assertIn(
                'XXTEST',
                schema['$defs']['record']['properties']['type']['enum'],
            )
            validator = self._validator()
            validator.validate(
                {'x': {'type': 'XXTEST', 'ttl': 300, 'values': ['anything']}}
            )
            validator.validate(
                {
                    'x': {
                        'type': 'XXTEST',
                        'ttl': 300,
                        'values': [{'any': 'shape'}, 42],
                    }
                }
            )
        finally:
            del Record._CLASSES['XXTEST']

    def test_round_trip_zone_fixtures(self):
        # zone YAML files octoDNS accepts today must also pass the schema
        validator = self._validator()
        for path in (
            'tests/config/unit.tests.yaml',
            'tests/config/dynamic.tests.yaml',
            'tests/config/subzone.unit.tests.yaml',
            'tests/config/dynamic-arpa/unit.tests.yaml',
        ):
            with open(path) as fh:
                data = safe_load(fh.read())
            errors = list(validator.iter_errors(data))
            self.assertEqual(
                [], errors, f'{path} failed schema validation: {errors}'
            )

    def test_cmd_schema_stdout(self):
        buf = StringIO()
        with patch('sys.argv', ['octodns-schema']), patch('sys.stdout', buf):
            schema_main()
        schema = json.loads(buf.getvalue())
        jsonschema.Draft202012Validator.check_schema(schema)

    def test_cmd_schema_output_file(self):
        with TemporaryDirectory() as tmp:
            path = f'{tmp}/schema.json'
            with patch('sys.argv', ['octodns-schema', '--output', path]):
                schema_main()
            with open(path) as fh:
                schema = json.load(fh)
            jsonschema.Draft202012Validator.check_schema(schema)

    def test_valid_ds_record_legacy(self):
        # deprecated legacy form — still valid until 2.0
        self._validator().validate(
            {
                'ds': {
                    'type': 'DS',
                    'ttl': 3600,
                    'values': [
                        {
                            'flags': 60485,
                            'protocol': 5,
                            'algorithm': 1,
                            'public_key': (
                                '2BB183AF5F22588179A53B0A98631FAD1A292118'
                            ),
                        }
                    ],
                }
            }
        )
