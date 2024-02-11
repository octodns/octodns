#
#
#

from unittest import TestCase

from helpers import DynamicProvider, SimpleProvider

from octodns.idna import idna_encode
from octodns.record import Record
from octodns.record.a import ARecord, Ipv4Value
from octodns.record.aaaa import AaaaRecord
from octodns.record.cname import CnameRecord
from octodns.record.dynamic import (
    _Dynamic,
    _DynamicMixin,
    _DynamicPool,
    _DynamicRule,
)
from octodns.record.exception import ValidationError
from octodns.zone import Zone


class TestRecordDynamic(TestCase):
    zone = Zone('unit.tests.', [])

    def test_dynamic_record_copy(self):
        a_data = {
            'dynamic': {
                'pools': {'one': {'values': [{'value': '3.3.3.3'}]}},
                'rules': [{'pool': 'one'}],
            },
            'octodns': {'healthcheck': {'protocol': 'TCP', 'port': 80}},
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        record1 = Record.new(self.zone, 'a', a_data)
        record2 = record1.copy()
        self.assertEqual(record1.octodns, record2.octodns)

    def test_healthcheck(self):
        new = Record.new(
            self.zone,
            'a',
            {
                'ttl': 44,
                'type': 'A',
                'value': '1.2.3.4',
                'octodns': {
                    'healthcheck': {
                        'path': '/_ready',
                        'host': 'bleep.bloop',
                        'protocol': 'HTTP',
                        'port': 8080,
                    }
                },
            },
        )
        self.assertEqual('/_ready', new.healthcheck_path)
        self.assertEqual('bleep.bloop', new.healthcheck_host())
        self.assertEqual('HTTP', new.healthcheck_protocol)
        self.assertEqual(8080, new.healthcheck_port)

        # empty host value in healthcheck
        new = Record.new(
            self.zone,
            'a',
            {
                'ttl': 44,
                'type': 'A',
                'value': '1.2.3.4',
                'octodns': {
                    'healthcheck': {
                        'path': '/_ready',
                        'host': None,
                        'protocol': 'HTTP',
                        'port': 8080,
                    }
                },
            },
        )
        self.assertEqual('1.2.3.4', new.healthcheck_host(value="1.2.3.4"))

        new = Record.new(
            self.zone, 'a', {'ttl': 44, 'type': 'A', 'value': '1.2.3.4'}
        )
        self.assertEqual('/_dns', new.healthcheck_path)
        self.assertEqual('a.unit.tests', new.healthcheck_host())
        self.assertEqual('HTTPS', new.healthcheck_protocol)
        self.assertEqual(443, new.healthcheck_port)

    def test_healthcheck_tcp(self):
        new = Record.new(
            self.zone,
            'a',
            {
                'ttl': 44,
                'type': 'A',
                'value': '1.2.3.4',
                'octodns': {
                    'healthcheck': {
                        'path': '/ignored',
                        'host': 'completely.ignored',
                        'protocol': 'TCP',
                        'port': 8080,
                    }
                },
            },
        )
        self.assertIsNone(new.healthcheck_path)
        self.assertIsNone(new.healthcheck_host())
        self.assertEqual('TCP', new.healthcheck_protocol)
        self.assertEqual(8080, new.healthcheck_port)

        new = Record.new(
            self.zone,
            'a',
            {
                'ttl': 44,
                'type': 'A',
                'value': '1.2.3.4',
                'octodns': {'healthcheck': {'protocol': 'TCP'}},
            },
        )
        self.assertIsNone(new.healthcheck_path)
        self.assertIsNone(new.healthcheck_host())
        self.assertEqual('TCP', new.healthcheck_protocol)
        self.assertEqual(443, new.healthcheck_port)

    def test_simple_a_weighted(self):
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'weight': 10, 'value': '3.3.3.3'}]},
                    'two': {
                        # Testing out of order value sorting here
                        'values': [{'value': '5.5.5.5'}, {'value': '4.4.4.4'}]
                    },
                    'three': {
                        'values': [
                            {'weight': 10, 'value': '4.4.4.4'},
                            {'weight': 12, 'value': '5.5.5.5'},
                        ]
                    },
                },
                'rules': [
                    {'geos': ['AF', 'EU'], 'pool': 'three'},
                    {'geos': ['NA-US-CA'], 'pool': 'two'},
                    {'pool': 'one'},
                ],
            },
            'ttl': 60,
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        a = ARecord(self.zone, 'weighted', a_data)
        self.assertEqual('A', a._type)
        self.assertEqual(a_data['ttl'], a.ttl)
        self.assertEqual(a_data['values'], a.values)

        dynamic = a.dynamic
        self.assertTrue(dynamic)

        pools = dynamic.pools
        self.assertTrue(pools)
        self.assertEqual(
            {'value': '3.3.3.3', 'weight': 1, 'status': 'obey'},
            pools['one'].data['values'][0],
        )
        self.assertEqual(
            [
                {'value': '4.4.4.4', 'weight': 1, 'status': 'obey'},
                {'value': '5.5.5.5', 'weight': 1, 'status': 'obey'},
            ],
            pools['two'].data['values'],
        )
        self.assertEqual(
            [
                {'weight': 10, 'value': '4.4.4.4', 'status': 'obey'},
                {'weight': 12, 'value': '5.5.5.5', 'status': 'obey'},
            ],
            pools['three'].data['values'],
        )

        rules = dynamic.rules
        self.assertTrue(rules)
        self.assertEqual(a_data['dynamic']['rules'][0], rules[0].data)

        # smoke test of _DynamicMixin.__repr__
        a.__repr__()
        delattr(a, 'values')
        a.value = 'abc'
        a.__repr__()

    def test_simple_aaaa_weighted(self):
        aaaa_data = {
            'dynamic': {
                'pools': {
                    'one': '2601:642:500:e210:62f8:1dff:feb8:9473',
                    'two': [
                        '2601:642:500:e210:62f8:1dff:feb8:9474',
                        '2601:642:500:e210:62f8:1dff:feb8:9475',
                    ],
                    'three': {
                        1: '2601:642:500:e210:62f8:1dff:feb8:9476',
                        2: '2601:642:500:e210:62f8:1dff:feb8:9477',
                    },
                },
                'rules': [{'pools': ['three', 'two', 'one']}],
            },
            'ttl': 60,
            'values': [
                '2601:642:500:e210:62f8:1dff:feb8:9471',
                '2601:642:500:e210:62f8:1dff:feb8:9472',
            ],
        }
        aaaa_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [
                            {'value': '2601:642:500:e210:62f8:1dff:feb8:9473'}
                        ]
                    },
                    'two': {
                        # Testing out of order value sorting here
                        'values': [
                            {'value': '2601:642:500:e210:62f8:1dff:feb8:9475'},
                            {'value': '2601:642:500:e210:62f8:1dff:feb8:9474'},
                        ]
                    },
                    'three': {
                        'values': [
                            {
                                'weight': 10,
                                'value': '2601:642:500:e210:62f8:1dff:feb8:9476',
                            },
                            {
                                'weight': 12,
                                'value': '2601:642:500:e210:62f8:1dff:feb8:9477',
                            },
                        ]
                    },
                },
                'rules': [
                    {'geos': ['AF', 'EU'], 'pool': 'three'},
                    {'geos': ['NA-US-CA'], 'pool': 'two'},
                    {'pool': 'one'},
                ],
            },
            'ttl': 60,
            'values': [
                '2601:642:500:e210:62f8:1dff:feb8:9471',
                '2601:642:500:e210:62f8:1dff:feb8:9472',
            ],
        }
        aaaa = AaaaRecord(self.zone, 'weighted', aaaa_data)
        self.assertEqual('AAAA', aaaa._type)
        self.assertEqual(aaaa_data['ttl'], aaaa.ttl)
        self.assertEqual(aaaa_data['values'], aaaa.values)

        dynamic = aaaa.dynamic
        self.assertTrue(dynamic)

        pools = dynamic.pools
        self.assertTrue(pools)
        self.assertEqual(
            {
                'value': '2601:642:500:e210:62f8:1dff:feb8:9473',
                'weight': 1,
                'status': 'obey',
            },
            pools['one'].data['values'][0],
        )
        self.assertEqual(
            [
                {
                    'value': '2601:642:500:e210:62f8:1dff:feb8:9474',
                    'weight': 1,
                    'status': 'obey',
                },
                {
                    'value': '2601:642:500:e210:62f8:1dff:feb8:9475',
                    'weight': 1,
                    'status': 'obey',
                },
            ],
            pools['two'].data['values'],
        )
        self.assertEqual(
            [
                {
                    'weight': 10,
                    'value': '2601:642:500:e210:62f8:1dff:feb8:9476',
                    'status': 'obey',
                },
                {
                    'weight': 12,
                    'value': '2601:642:500:e210:62f8:1dff:feb8:9477',
                    'status': 'obey',
                },
            ],
            pools['three'].data['values'],
        )

        rules = dynamic.rules
        self.assertTrue(rules)
        self.assertEqual(aaaa_data['dynamic']['rules'][0], rules[0].data)

    def test_simple_cname_weighted(self):
        cname_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': 'one.cname.target.'}]},
                    'two': {'values': [{'value': 'two.cname.target.'}]},
                    'three': {
                        'values': [
                            {'weight': 12, 'value': 'three-1.cname.target.'},
                            {'weight': 32, 'value': 'three-2.cname.target.'},
                        ]
                    },
                },
                'rules': [
                    {'geos': ['AF', 'EU'], 'pool': 'three'},
                    {'geos': ['NA-US-CA'], 'pool': 'two'},
                    {'pool': 'one'},
                ],
            },
            'ttl': 60,
            'value': 'cname.target.',
        }
        cname = CnameRecord(self.zone, 'weighted', cname_data)
        self.assertEqual('CNAME', cname._type)
        self.assertEqual(cname_data['ttl'], cname.ttl)
        self.assertEqual(cname_data['value'], cname.value)

        dynamic = cname.dynamic
        self.assertTrue(dynamic)

        pools = dynamic.pools
        self.assertTrue(pools)
        self.assertEqual(
            {'value': 'one.cname.target.', 'weight': 1, 'status': 'obey'},
            pools['one'].data['values'][0],
        )
        self.assertEqual(
            {'value': 'two.cname.target.', 'weight': 1, 'status': 'obey'},
            pools['two'].data['values'][0],
        )
        self.assertEqual(
            [
                {
                    'value': 'three-1.cname.target.',
                    'weight': 12,
                    'status': 'obey',
                },
                {
                    'value': 'three-2.cname.target.',
                    'weight': 32,
                    'status': 'obey',
                },
            ],
            pools['three'].data['values'],
        )

        rules = dynamic.rules
        self.assertTrue(rules)
        self.assertEqual(cname_data['dynamic']['rules'][0], rules[0].data)

    def test_dynamic_validation(self):
        # Missing pools
        a_data = {
            'dynamic': {'rules': [{'pool': 'one'}]},
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(
            ['missing pools', 'rule 1 undefined pool "one"'],
            ctx.exception.reasons,
        )

        # Empty pools
        a_data = {
            'dynamic': {'pools': {}, 'rules': [{'pool': 'one'}]},
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(
            ['missing pools', 'rule 1 undefined pool "one"'],
            ctx.exception.reasons,
        )

        # pools not a dict
        a_data = {
            'dynamic': {'pools': [], 'rules': [{'pool': 'one'}]},
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(
            ['pools must be a dict', 'rule 1 undefined pool "one"'],
            ctx.exception.reasons,
        )

        # Invalid addresses
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': 'this-aint-right'}]},
                    'two': {
                        'fallback': 'one',
                        'values': [
                            {'value': '4.4.4.4'},
                            {'value': 'nor-is-this'},
                        ],
                    },
                    'three': {
                        'fallback': 'two',
                        'values': [
                            {'weight': 1, 'value': '5.5.5.5'},
                            {'weight': 2, 'value': 'yet-another-bad-one'},
                        ],
                    },
                },
                'rules': [
                    {'geos': ['AF', 'EU'], 'pool': 'three'},
                    {'geos': ['NA-US-CA'], 'pool': 'two'},
                    {'pool': 'one'},
                ],
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(
            [
                'invalid IPv4 address "this-aint-right"',
                'invalid IPv4 address "yet-another-bad-one"',
                'invalid IPv4 address "nor-is-this"',
            ],
            ctx.exception.reasons,
        )

        # missing value(s)
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {},
                    'two': {
                        'values': [{'value': '4.4.4.4'}, {'value': '5.5.5.5'}]
                    },
                    'three': {
                        'values': [
                            {'weight': 1, 'value': '6.6.6.6'},
                            {'weight': 2, 'value': '7.7.7.7'},
                        ]
                    },
                },
                'rules': [
                    {'geos': ['AF', 'EU'], 'pool': 'three'},
                    {'geos': ['NA-US-CA'], 'pool': 'two'},
                    {'pool': 'one'},
                ],
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(
            ['pool "one" is missing values'], ctx.exception.reasons
        )

        # pool value not a dict
        a_data = {
            'dynamic': {
                'pools': {
                    'one': '',
                    'two': {
                        'values': [{'value': '4.4.4.4'}, {'value': '5.5.5.5'}]
                    },
                    'three': {
                        'values': [
                            {'weight': 1, 'value': '6.6.6.6'},
                            {'weight': 2, 'value': '7.7.7.7'},
                        ]
                    },
                },
                'rules': [
                    {'geos': ['AF', 'EU'], 'pool': 'three'},
                    {'geos': ['NA-US-CA'], 'pool': 'two'},
                    {'pool': 'one'},
                ],
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(['pool "one" must be a dict'], ctx.exception.reasons)

        # empty pool value
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {},
                    'two': {
                        'values': [{'value': '4.4.4.4'}, {'value': '5.5.5.5'}]
                    },
                    'three': {
                        'values': [
                            {'weight': 1, 'value': '6.6.6.6'},
                            {'weight': 2, 'value': '7.7.7.7'},
                        ]
                    },
                },
                'rules': [
                    {'geos': ['AF', 'EU'], 'pool': 'three'},
                    {'geos': ['NA-US-CA'], 'pool': 'two'},
                    {'pool': 'one'},
                ],
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(
            ['pool "one" is missing values'], ctx.exception.reasons
        )

        # invalid int weight
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': '3.3.3.3'}]},
                    'two': {
                        'values': [{'value': '4.4.4.4'}, {'value': '5.5.5.5'}]
                    },
                    'three': {
                        'values': [
                            {'weight': 1, 'value': '6.6.6.6'},
                            {'weight': 101, 'value': '7.7.7.7'},
                        ]
                    },
                },
                'rules': [
                    {'geos': ['AF', 'EU'], 'pool': 'three'},
                    {'geos': ['NA-US-CA'], 'pool': 'two'},
                    {'pool': 'one'},
                ],
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(
            ['invalid weight "101" in pool "three" value 2'],
            ctx.exception.reasons,
        )

        # invalid non-int weight
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': '3.3.3.3'}]},
                    'two': {
                        'values': [{'value': '4.4.4.4'}, {'value': '5.5.5.5'}]
                    },
                    'three': {
                        'values': [
                            {'weight': 1, 'value': '6.6.6.6'},
                            {'weight': 'foo', 'value': '7.7.7.7'},
                        ]
                    },
                },
                'rules': [
                    {'geos': ['AF', 'EU'], 'pool': 'three'},
                    {'geos': ['NA-US-CA'], 'pool': 'two'},
                    {'pool': 'one'},
                ],
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(
            ['invalid weight "foo" in pool "three" value 2'],
            ctx.exception.reasons,
        )

        # single value with weight!=1
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'weight': 12, 'value': '6.6.6.6'}]}
                },
                'rules': [{'pool': 'one'}],
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(
            ['pool "one" has single value with weight!=1'],
            ctx.exception.reasons,
        )

        # invalid fallback
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': '3.3.3.3'}]},
                    'two': {
                        'fallback': 'invalid',
                        'values': [{'value': '4.4.4.4'}, {'value': '5.5.5.5'}],
                    },
                    'three': {
                        'fallback': 'two',
                        'values': [
                            {'weight': 1, 'value': '6.6.6.6'},
                            {'weight': 5, 'value': '7.7.7.7'},
                        ],
                    },
                },
                'rules': [
                    {'geos': ['AF', 'EU'], 'pool': 'three'},
                    {'geos': ['NA-US-CA'], 'pool': 'two'},
                    {'pool': 'one'},
                ],
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(
            ['undefined fallback "invalid" for pool "two"'],
            ctx.exception.reasons,
        )

        # fallback loop
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'fallback': 'three',
                        'values': [{'value': '3.3.3.3'}],
                    },
                    'two': {
                        'fallback': 'one',
                        'values': [{'value': '4.4.4.4'}, {'value': '5.5.5.5'}],
                    },
                    'three': {
                        'fallback': 'two',
                        'values': [
                            {'weight': 1, 'value': '6.6.6.6'},
                            {'weight': 5, 'value': '7.7.7.7'},
                        ],
                    },
                },
                'rules': [
                    {'geos': ['AF', 'EU'], 'pool': 'three'},
                    {'geos': ['NA-US-CA'], 'pool': 'two'},
                    {'pool': 'one'},
                ],
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(
            [
                'loop in pool fallbacks: one -> three -> two',
                'loop in pool fallbacks: three -> two -> one',
                'loop in pool fallbacks: two -> one -> three',
            ],
            ctx.exception.reasons,
        )

        # multiple pool problems
        a_data = {
            'dynamic': {
                'pools': {
                    'one': '',
                    'two': {
                        'values': [{'value': '4.4.4.4'}, {'value': 'blip'}]
                    },
                    'three': {
                        'values': [
                            {'weight': 1},
                            {'weight': 5000, 'value': '7.7.7.7'},
                        ]
                    },
                },
                'rules': [
                    {'geos': ['AF', 'EU'], 'pool': 'three'},
                    {'geos': ['NA-US-CA'], 'pool': 'two'},
                    {'pool': 'one'},
                ],
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(
            [
                'pool "one" must be a dict',
                'missing value in pool "three" value 1',
                'invalid weight "5000" in pool "three" value 2',
                'invalid IPv4 address "blip"',
            ],
            ctx.exception.reasons,
        )

        # missing rules, and unused pools
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': '3.3.3.3'}]},
                    'two': {
                        'values': [{'value': '4.4.4.4'}, {'value': '5.5.5.5'}]
                    },
                }
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(
            ['missing rules', 'unused pools: "one", "two"'],
            ctx.exception.reasons,
        )

        # empty rules
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': '3.3.3.3'}]},
                    'two': {
                        'values': [{'value': '4.4.4.4'}, {'value': '5.5.5.5'}]
                    },
                },
                'rules': [],
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(
            ['missing rules', 'unused pools: "one", "two"'],
            ctx.exception.reasons,
        )

        # rules not a list/tuple
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': '3.3.3.3'}]},
                    'two': {
                        'values': [{'value': '4.4.4.4'}, {'value': '5.5.5.5'}]
                    },
                },
                'rules': {},
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(
            ['rules must be a list', 'unused pools: "one", "two"'],
            ctx.exception.reasons,
        )

        # rule without pool
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': '3.3.3.3'}]},
                    'two': {
                        'values': [{'value': '4.4.4.4'}, {'value': '5.5.5.5'}]
                    },
                },
                'rules': [{'geos': ['NA-US-CA']}, {'pool': 'one'}],
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(
            ['rule 1 missing pool', 'unused pools: "two"'],
            ctx.exception.reasons,
        )

        # rule with non-string pools
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': '3.3.3.3'}]},
                    'two': {
                        'values': [{'value': '4.4.4.4'}, {'value': '5.5.5.5'}]
                    },
                },
                'rules': [{'geos': ['NA-US-CA'], 'pool': []}, {'pool': 'one'}],
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(
            ['rule 1 invalid pool "[]"', 'unused pools: "two"'],
            ctx.exception.reasons,
        )

        # rule references non-existent pool
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': '3.3.3.3'}]},
                    'two': {
                        'values': [{'value': '4.4.4.4'}, {'value': '5.5.5.5'}]
                    },
                },
                'rules': [
                    {'geos': ['NA-US-CA'], 'pool': 'non-existent'},
                    {'pool': 'one'},
                ],
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(
            ["rule 1 undefined pool \"non-existent\"", 'unused pools: "two"'],
            ctx.exception.reasons,
        )

        # rule with invalid subnets
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': '3.3.3.3'}]},
                    'two': {
                        'values': [{'value': '4.4.4.4'}, {'value': '5.5.5.5'}]
                    },
                },
                'rules': [
                    {'subnets': '10.1.0.0/16', 'pool': 'two'},
                    {'pool': 'one'},
                ],
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(
            ['rule 1 subnets must be a list'], ctx.exception.reasons
        )

        # rule with invalid subnet
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': '3.3.3.3'}]},
                    'two': {
                        'values': [{'value': '4.4.4.4'}, {'value': '5.5.5.5'}]
                    },
                },
                'rules': [
                    {'subnets': ['invalid'], 'pool': 'two'},
                    {'pool': 'one'},
                ],
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(
            ['rule 1 invalid subnet "invalid"'], ctx.exception.reasons
        )

        # rule with invalid geos
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': '3.3.3.3'}]},
                    'two': {
                        'values': [{'value': '4.4.4.4'}, {'value': '5.5.5.5'}]
                    },
                },
                'rules': [{'geos': 'NA-US-CA', 'pool': 'two'}, {'pool': 'one'}],
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(['rule 1 geos must be a list'], ctx.exception.reasons)

        # rule with invalid geo
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': '3.3.3.3'}]},
                    'two': {
                        'values': [{'value': '4.4.4.4'}, {'value': '5.5.5.5'}]
                    },
                },
                'rules': [
                    {'geos': ['invalid'], 'pool': 'two'},
                    {'pool': 'one'},
                ],
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(
            ['rule 1 unknown continent code "invalid"'], ctx.exception.reasons
        )

        # multiple default rules
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': '3.3.3.3'}]},
                    'two': {
                        'values': [{'value': '4.4.4.4'}, {'value': '5.5.5.5'}]
                    },
                },
                'rules': [{'pool': 'two'}, {'pool': 'one'}],
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(['rule 2 duplicate default'], ctx.exception.reasons)

        # repeated pool in rules
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': '3.3.3.3'}]},
                    'two': {
                        'values': [{'value': '4.4.4.4'}, {'value': '5.5.5.5'}]
                    },
                },
                'rules': [
                    {'geos': ['EU'], 'pool': 'two'},
                    {'geos': ['AF'], 'pool': 'one'},
                    {'geos': ['OC'], 'pool': 'one'},
                    {'pool': 'one'},
                ],
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(
            ['rule 3 invalid, target pool "one" reused'], ctx.exception.reasons
        )

        # Repeated pool is OK if later one is a default
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': '3.3.3.3'}]},
                    'two': {
                        'values': [{'value': '4.4.4.4'}, {'value': '5.5.5.5'}]
                    },
                },
                'rules': [
                    {'geos': ['EU-GB'], 'pool': 'one'},
                    {'geos': ['EU'], 'pool': 'two'},
                    {'pool': 'one'},
                ],
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        # This should be valid, no exception
        Record.new(self.zone, 'bad', a_data)

        # invalid status
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': '2.2.2.2', 'status': 'none'}]}
                },
                'rules': [{'pool': 'one'}],
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertIn('invalid status', ctx.exception.reasons[0])

    def test_dynamic_lenient(self):
        # Missing pools
        a_data = {
            'dynamic': {
                'rules': [{'geos': ['EU'], 'pool': 'two'}, {'pool': 'one'}]
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        a = Record.new(self.zone, 'bad', a_data, lenient=True)
        self.assertEqual(
            {'pools': {}, 'rules': a_data['dynamic']['rules']},
            a._data()['dynamic'],
        )

        # Missing rule
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': '3.3.3.3'}]},
                    'two': {
                        'values': [
                            {'value': '4.4.4.4'},
                            {'value': '5.5.5.5', 'weight': 2},
                        ]
                    },
                }
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        a = Record.new(self.zone, 'bad', a_data, lenient=True)
        self.assertEqual(
            {
                'pools': {
                    'one': {
                        'fallback': None,
                        'values': [
                            {'value': '3.3.3.3', 'weight': 1, 'status': 'obey'}
                        ],
                    },
                    'two': {
                        'fallback': None,
                        'values': [
                            {'value': '4.4.4.4', 'weight': 1, 'status': 'obey'},
                            {'value': '5.5.5.5', 'weight': 2, 'status': 'obey'},
                        ],
                    },
                },
                'rules': [],
            },
            a._data()['dynamic'],
        )

        # rule without pool
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': '3.3.3.3'}]},
                    'two': {
                        'values': [
                            {'value': '4.4.4.4'},
                            {'value': '5.5.5.5', 'weight': 2},
                        ]
                    },
                },
                'rules': [{'geos': ['EU'], 'pool': 'two'}, {}],
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        a = Record.new(self.zone, 'bad', a_data, lenient=True)
        self.assertEqual(
            {
                'pools': {
                    'one': {
                        'fallback': None,
                        'values': [
                            {'value': '3.3.3.3', 'weight': 1, 'status': 'obey'}
                        ],
                    },
                    'two': {
                        'fallback': None,
                        'values': [
                            {'value': '4.4.4.4', 'weight': 1, 'status': 'obey'},
                            {'value': '5.5.5.5', 'weight': 2, 'status': 'obey'},
                        ],
                    },
                },
                'rules': a_data['dynamic']['rules'],
            },
            a._data()['dynamic'],
        )

    def test_dynamic_changes(self):
        simple = SimpleProvider()
        dynamic = DynamicProvider()

        a_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': '3.3.3.3'}]},
                    'two': {
                        'values': [{'value': '4.4.4.4'}, {'value': '5.5.5.5'}]
                    },
                },
                'rules': [{'geos': ['EU'], 'pool': 'two'}, {'pool': 'one'}],
            },
            'ttl': 60,
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        a = ARecord(self.zone, 'weighted', a_data)
        dup = ARecord(self.zone, 'weighted', a_data)

        b_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': '3.3.3.3'}]},
                    'two': {
                        'values': [
                            {'value': '4.4.4.4', 'weight': 2},
                            {'value': '5.5.5.5'},
                        ]
                    },
                },
                'rules': [{'geos': ['EU'], 'pool': 'two'}, {'pool': 'one'}],
            },
            'ttl': 60,
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        b = ARecord(self.zone, 'weighted', b_data)

        c_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': '3.3.3.3'}]},
                    'two': {
                        'values': [{'value': '4.4.4.4'}, {'value': '5.5.5.5'}]
                    },
                },
                'rules': [{'geos': ['NA'], 'pool': 'two'}, {'pool': 'one'}],
            },
            'ttl': 60,
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        c = ARecord(self.zone, 'weighted', c_data)

        # a changes a (identical dup) is never true
        self.assertFalse(a.changes(dup, simple))
        self.assertFalse(a.changes(dup, dynamic))

        # a changes b is not true for simple
        self.assertFalse(a.changes(b, simple))
        # but is true for dynamic
        update = a.changes(b, dynamic)
        self.assertEqual(a, update.existing)
        self.assertEqual(b, update.new)
        # transitive
        self.assertFalse(b.changes(a, simple))
        update = b.changes(a, dynamic)
        self.assertEqual(a, update.existing)
        self.assertEqual(b, update.new)

        # same for a change c
        self.assertFalse(a.changes(c, simple))
        self.assertTrue(a.changes(c, dynamic))
        self.assertFalse(c.changes(a, simple))
        self.assertTrue(c.changes(a, dynamic))

        # smoke test some of the equiality bits
        self.assertEqual(a.dynamic.pools, a.dynamic.pools)
        self.assertEqual(a.dynamic.pools['one'], a.dynamic.pools['one'])
        self.assertNotEqual(a.dynamic.pools['one'], a.dynamic.pools['two'])
        self.assertEqual(a.dynamic.rules, a.dynamic.rules)
        self.assertEqual(a.dynamic.rules[0], a.dynamic.rules[0])
        self.assertNotEqual(a.dynamic.rules[0], c.dynamic.rules[0])

    def test_dynamic_and_geo_validation(self):
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': '3.3.3.3'}]},
                    'two': {
                        'values': [{'value': '5.5.5.5'}, {'value': '4.4.4.4'}]
                    },
                    'three': {
                        'values': [
                            {'weight': 10, 'value': '4.4.4.4'},
                            {'weight': 12, 'value': '5.5.5.5'},
                        ]
                    },
                },
                'rules': [
                    {'geos': ['AF', 'EU'], 'pool': 'three'},
                    {'geos': ['NA-US-CA'], 'pool': 'two'},
                    {'pool': 'one'},
                ],
            },
            'geo': {'NA': ['1.2.3.5'], 'NA-US': ['1.2.3.5', '1.2.3.6']},
            'type': 'A',
            'ttl': 60,
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(
            ['"dynamic" record with "geo" content'], ctx.exception.reasons
        )

    def test_dynamic_eqs(self):
        pool_one = _DynamicPool(
            'one', {'values': [{'value': '1.2.3.4'}]}, Ipv4Value
        )
        pool_two = _DynamicPool(
            'two', {'values': [{'value': '1.2.3.5'}]}, Ipv4Value
        )
        self.assertEqual(pool_one, pool_one)
        self.assertNotEqual(pool_one, pool_two)
        self.assertNotEqual(pool_one, 42)

        pools = {'one': pool_one, 'two': pool_two}
        rule_one = _DynamicRule(0, {'pool': 'one'})
        rule_two = _DynamicRule(1, {'pool': 'two'})
        self.assertEqual(rule_one, rule_one)
        self.assertNotEqual(rule_one, rule_two)
        self.assertNotEqual(rule_one, 42)
        rules = [rule_one, rule_two]

        dynamic = _Dynamic(pools, rules)
        other = _Dynamic({}, [])
        self.assertEqual(dynamic, dynamic)
        self.assertNotEqual(dynamic, other)
        self.assertNotEqual(dynamic, 42)

    def test_dynamic_cname_idna(self):
        a_utf8 = 'natación.mx.'
        a_encoded = idna_encode(a_utf8)
        b_utf8 = 'гэрбүл.mn.'
        b_encoded = idna_encode(b_utf8)
        cname_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        # Testing out of order value sorting here
                        'values': [
                            {'value': 'b.unit.tests.'},
                            {'value': 'a.unit.tests.'},
                        ]
                    },
                    'two': {
                        'values': [
                            # some utf8 values we expect to be idna encoded
                            {'weight': 10, 'value': a_utf8},
                            {'weight': 12, 'value': b_utf8},
                        ]
                    },
                },
                'rules': [
                    {'geos': ['NA-US-CA'], 'pool': 'two'},
                    {'pool': 'one'},
                ],
            },
            'type': 'CNAME',
            'ttl': 60,
            'value': a_utf8,
        }
        cname = Record.new(self.zone, 'cname', cname_data)
        self.assertEqual(a_encoded, cname.value)
        self.assertEqual(
            {
                'fallback': None,
                'values': [
                    {'weight': 1, 'value': 'a.unit.tests.', 'status': 'obey'},
                    {'weight': 1, 'value': 'b.unit.tests.', 'status': 'obey'},
                ],
            },
            cname.dynamic.pools['one'].data,
        )
        self.assertEqual(
            {
                'fallback': None,
                'values': [
                    {'weight': 12, 'value': b_encoded, 'status': 'obey'},
                    {'weight': 10, 'value': a_encoded, 'status': 'obey'},
                ],
            },
            cname.dynamic.pools['two'].data,
        )

    def test_dynamic_mixin_validate_rules(self):
        # this one is fine we get more generic with subsequent rules
        pools = {'iad', 'sfo'}
        rules = [
            {'geos': ('AS', 'NA-CA', 'NA-US-OR'), 'pool': 'sfo'},
            {'geos': ('EU', 'NA'), 'pool': 'iad'},
            {'pool': 'iad'},
        ]
        reasons, pools_seen = _DynamicMixin._validate_rules(pools, rules)
        self.assertFalse(reasons)
        self.assertEqual({'sfo', 'iad'}, pools_seen)

        # this one targets NA in rule 0 and then NA-Ca in rule 1
        pools = {'iad', 'sfo'}
        rules = [
            {'geos': ('AS', 'NA'), 'pool': 'sfo'},
            {'geos': ('EU', 'NA-CA'), 'pool': 'iad'},
            {'pool': 'iad'},
        ]
        reasons, pools_seen = _DynamicMixin._validate_rules(pools, rules)
        self.assertEqual(
            [
                'rule 2 targets geo NA-CA which is more specific than the previously seen NA in rule 1'
            ],
            reasons,
        )

        # this one targets NA and NA-US in rule 0
        pools = {'iad', 'sfo'}
        rules = [
            {'geos': ('AS', 'NA-US', 'NA'), 'pool': 'sfo'},
            {'pool': 'iad'},
        ]
        reasons, pools_seen = _DynamicMixin._validate_rules(pools, rules)
        self.assertEqual(
            [
                'rule 1 targets geo NA-US which is more specific than the previously seen NA in rule 1'
            ],
            reasons,
        )

        # this one targets the same geo in multiple rules
        pools = {'iad', 'sfo'}
        rules = [
            {'geos': ('AS', 'NA'), 'pool': 'sfo'},
            {'geos': ('EU', 'NA'), 'pool': 'iad'},
            {'pool': 'iad'},
        ]
        reasons, pools_seen = _DynamicMixin._validate_rules(pools, rules)
        self.assertEqual(
            ['rule 2 targets geo NA which has previously been seen in rule 1'],
            reasons,
        )

        # this one doesn't have a catch-all rule at the end
        pools = {'iad', 'sfo'}
        rules = [
            {'geos': ('AS', 'NA-CA', 'NA-US-OR'), 'pool': 'sfo'},
            {'geos': ('EU', 'NA'), 'pool': 'iad'},
        ]
        reasons, pools_seen = _DynamicMixin._validate_rules(pools, rules)
        self.assertEqual(
            ['final rule has "subnets" and/or "geos" and is not catchall'],
            reasons,
        )

    def test_dynamic_subnet_rule_ordering(self):
        # boiler plate
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': '3.3.3.3'}]},
                    'two': {
                        'values': [{'value': '4.4.4.4'}, {'value': '5.5.5.5'}]
                    },
                    'three': {'values': [{'value': '2.2.2.2'}]},
                }
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        dynamic = a_data['dynamic']

        def validate_rules(rules):
            dynamic['rules'] = rules
            with self.assertRaises(ValidationError) as ctx:
                Record.new(self.zone, 'bad', a_data)
            return ctx.exception.reasons

        # valid subnet-only → subnet+geo
        dynamic['rules'] = [
            {'subnets': ['10.1.0.0/16'], 'pool': 'one'},
            {'subnets': ['11.1.0.0/16'], 'geos': ['NA'], 'pool': 'two'},
            {'pool': 'three'},
        ]
        record = Record.new(self.zone, 'good', a_data)
        self.assertEqual(
            '10.1.0.0/16', record.dynamic.rules[0].data['subnets'][0]
        )

        # geo-only → subnet-only
        self.assertEqual(
            [
                'rule 2 with only subnet targeting should appear before all geo targeting rules'
            ],
            validate_rules(
                [
                    {'geos': ['NA'], 'pool': 'two'},
                    {'subnets': ['10.1.0.0/16'], 'pool': 'one'},
                    {'pool': 'three'},
                ]
            ),
        )

        # geo-only → subnet+geo
        self.assertEqual(
            [
                'rule 2 with subnet(s) and geo(s) should appear before all geo-only rules'
            ],
            validate_rules(
                [
                    {'geos': ['NA'], 'pool': 'two'},
                    {'subnets': ['10.1.0.0/16'], 'geos': ['AS'], 'pool': 'one'},
                    {'pool': 'three'},
                ]
            ),
        )

        # subnet+geo → subnet-only
        self.assertEqual(
            [
                'rule 2 with only subnet targeting should appear before all geo targeting rules'
            ],
            validate_rules(
                [
                    {'subnets': ['11.1.0.0/16'], 'geos': ['NA'], 'pool': 'two'},
                    {'subnets': ['10.1.0.0/16'], 'pool': 'one'},
                    {'pool': 'three'},
                ]
            ),
        )

        # geo-only → subnet+geo → subnet-only
        self.assertEqual(
            [
                'rule 2 with subnet(s) and geo(s) should appear before all geo-only rules',
                'rule 3 with only subnet targeting should appear before all geo targeting rules',
            ],
            validate_rules(
                [
                    {'geos': ['NA'], 'pool': 'two'},
                    {'subnets': ['10.1.0.0/16'], 'geos': ['AS'], 'pool': 'one'},
                    {'subnets': ['11.1.0.0/16'], 'pool': 'three'},
                    {'pool': 'one'},
                ]
            ),
        )

    def test_dynanic_subnet_ordering(self):
        # boiler plate
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {'values': [{'value': '3.3.3.3'}]},
                    'two': {
                        'values': [{'value': '4.4.4.4'}, {'value': '5.5.5.5'}]
                    },
                    'three': {'values': [{'value': '2.2.2.2'}]},
                }
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        }
        dynamic = a_data['dynamic']

        def validate_rules(rules):
            dynamic['rules'] = rules
            with self.assertRaises(ValidationError) as ctx:
                Record.new(self.zone, 'bad', a_data)
            return ctx.exception.reasons

        # duplicate subnet
        self.assertEqual(
            [
                'rule 2 targets subnet 10.1.0.0/16 which has previously been seen in rule 1'
            ],
            validate_rules(
                [
                    {'subnets': ['10.1.0.0/16'], 'pool': 'two'},
                    {'subnets': ['10.1.0.0/16'], 'pool': 'one'},
                    {'pool': 'three'},
                ]
            ),
        )

        # more specific subnet than previous
        self.assertEqual(
            [
                'rule 2 targets subnet 10.1.1.0/24 which is more specific than the previously seen 10.1.0.0/16 in rule 1'
            ],
            validate_rules(
                [
                    {'subnets': ['10.1.0.0/16'], 'pool': 'two'},
                    {'subnets': ['10.1.1.0/24'], 'pool': 'one'},
                    {'pool': 'three'},
                ]
            ),
        )

        # sub-subnet in the same rule
        self.assertEqual(
            [
                'rule 1 targets subnet 10.1.1.0/24 which is more specific than the previously seen 10.1.0.0/16 in rule 1'
            ],
            validate_rules(
                [
                    {'subnets': ['10.1.0.0/16', '10.1.1.0/24'], 'pool': 'two'},
                    {'subnets': ['11.1.0.0/16'], 'pool': 'one'},
                    {'pool': 'three'},
                ]
            ),
        )

    def test_dynamic_subnet_mixed_versions(self):
        # mixed IPv4 and IPv6 subnets should not raise a validation error
        Record.new(
            self.zone,
            'good',
            {
                'dynamic': {
                    'pools': {
                        'one': {'values': [{'value': '1.1.1.1'}]},
                        'two': {'values': [{'value': '2.2.2.2'}]},
                    },
                    'rules': [
                        {'subnets': ['10.1.0.0/16', '1::/66'], 'pool': 'one'},
                        {'pool': 'two'},
                    ],
                },
                'ttl': 60,
                'type': 'A',
                'values': ['2.2.2.2'],
            },
        )

        Record.new(
            self.zone,
            'good',
            {
                'dynamic': {
                    'pools': {
                        'one': {'values': [{'value': '1.1.1.1'}]},
                        'two': {'values': [{'value': '2.2.2.2'}]},
                    },
                    'rules': [
                        {'subnets': ['10.1.0.0/16'], 'pool': 'one'},
                        {'subnets': ['1::/66'], 'pool': 'two'},
                        {'pool': 'two'},
                    ],
                },
                'ttl': 60,
                'type': 'A',
                'values': ['2.2.2.2'],
            },
        )
