#
#
#

from unittest import TestCase

from helpers import SimpleProvider

from octodns.record import Record
from octodns.source.tinydns import TinyDnsFileSource
from octodns.zone import Zone


class TestTinyDnsFileSource(TestCase):
    source = TinyDnsFileSource('test', './tests/zones/tinydns')

    def test_populate_normal(self):
        got = Zone('example.com.', [])
        self.source.populate(got)
        self.assertEqual(30, len(got.records))

        expected = Zone('example.com.', [])
        for name, data in (
            ('', {'type': 'A', 'ttl': 30, 'values': ['10.2.3.4', '10.2.3.5']}),
            (
                '',
                {
                    'type': 'NS',
                    'ttl': 31,
                    'values': [
                        'a.ns.example.com.',
                        'b.ns.example.com.',
                        'ns1.ns.com.',
                        'ns2.ns.com.',
                    ],
                },
            ),
            (
                'sub',
                {
                    'type': 'NS',
                    'ttl': 30,
                    'values': ['ns3.ns.com.', 'ns4.ns.com.'],
                },
            ),
            ('www', {'type': 'A', 'ttl': 3600, 'value': '10.2.3.6'}),
            (
                'cname',
                {'type': 'CNAME', 'ttl': 3600, 'value': 'www.example.com.'},
            ),
            (
                'cname2',
                {'type': 'CNAME', 'ttl': 48, 'value': 'www2.example.com.'},
            ),
            (
                'some-host-abc123',
                {'type': 'A', 'ttl': 1800, 'value': '10.2.3.7'},
            ),
            ('has-dup-def123', {'type': 'A', 'ttl': 3600, 'value': '10.2.3.8'}),
            ('www.sub', {'type': 'A', 'ttl': 3600, 'value': '1.2.3.4'}),
            ('has-dup-def456', {'type': 'A', 'ttl': 3600, 'value': '10.2.3.8'}),
            (
                '',
                {
                    'type': 'MX',
                    'ttl': 3600,
                    'values': [
                        {
                            'preference': 10,
                            'exchange': 'smtp-1-host.example.com.',
                        },
                        {
                            'preference': 0,
                            'exchange': 'smtp-2-host.example.com.',
                        },
                    ],
                },
            ),
            (
                'smtp',
                {
                    'type': 'MX',
                    'ttl': 1800,
                    'values': [
                        {
                            'preference': 30,
                            'exchange': 'smtp-3-host.mx.example.com.',
                        },
                        {
                            'preference': 40,
                            'exchange': 'smtp-4-host.mx.example.com.',
                        },
                    ],
                },
            ),
            ('', {'type': 'TXT', 'ttl': 300, 'value': 'test TXT'}),
            ('colon', {'type': 'TXT', 'ttl': 300, 'value': 'test : TXT'}),
            ('nottl', {'type': 'TXT', 'ttl': 3600, 'value': 'nottl test TXT'}),
            (
                'ipv6-3',
                {
                    'type': 'AAAA',
                    'ttl': 300,
                    'value': '2a02:1348:017c:d5d0:0024:19ff:fef3:5742',
                },
            ),
            (
                'ipv6-6',
                {
                    'type': 'AAAA',
                    'ttl': 3600,
                    'value': '2a02:1348:017c:d5d0:0024:19ff:fef3:5743',
                },
            ),
            (
                'semicolon',
                {
                    'type': 'TXT',
                    'ttl': 300,
                    'value': 'v=DKIM1\\; k=rsa\\; p=blah',
                },
            ),
            ('b.ns', {'type': 'A', 'ttl': 31, 'value': '43.44.45.46'}),
            ('a.ns', {'type': 'A', 'ttl': 3600, 'value': '42.43.44.45'}),
            (
                'smtp-3-host.mx',
                {'type': 'A', 'ttl': 1800, 'value': '21.22.23.24'},
            ),
            (
                'smtp-4-host.mx',
                {'type': 'A', 'ttl': 1800, 'value': '22.23.24.25'},
            ),
            ('ns5.ns', {'type': 'A', 'ttl': 30, 'value': '14.15.16.17'}),
            ('ns6.ns', {'type': 'A', 'ttl': 30, 'value': '15.16.17.18'}),
            (
                'other',
                {
                    'type': 'NS',
                    'ttl': 30,
                    'values': ['ns5.ns.example.com.', 'ns6.ns.example.com.'],
                },
            ),
            (
                '_a._tcp',
                {
                    'type': 'SRV',
                    'ttl': 43,
                    'values': [
                        {
                            'priority': 0,
                            'weight': 0,
                            'port': 8888,
                            'target': 'target.srv.example.com.',
                        },
                        {
                            'priority': 10,
                            'weight': 50,
                            'port': 8080,
                            'target': 'target.somewhere.else.',
                        },
                    ],
                },
            ),
            ('target.srv', {'type': 'A', 'ttl': 43, 'value': '56.57.58.59'}),
            (
                '_b._tcp',
                {
                    'type': 'SRV',
                    'ttl': 3600,
                    'values': [
                        {
                            'priority': 0,
                            'weight': 0,
                            'port': 9999,
                            'target': 'target.srv.example.com.',
                        }
                    ],
                },
            ),
            (
                'arbitrary-sshfp',
                {
                    'type': 'SSHFP',
                    'ttl': 45,
                    'values': [
                        {
                            'algorithm': 1,
                            'fingerprint_type': 2,
                            'fingerprint': '00479b27',
                        },
                        {
                            'algorithm': 2,
                            'fingerprint_type': 2,
                            'fingerprint': '00479a28',
                        },
                    ],
                },
            ),
            ('arbitrary-a', {'type': 'A', 'ttl': 3600, 'value': '80.81.82.83'}),
        ):
            record = Record.new(expected, name, data)
            expected.add_record(record)

        changes = expected.changes(got, SimpleProvider())
        self.assertEqual([], changes)

    def test_populate_normal_sub1(self):
        got = Zone('asdf.subtest.com.', [])
        self.source.populate(got)
        self.assertEqual(1, len(got.records))

        expected = Zone('asdf.subtest.com.', [])
        for name, data in (
            ('a3', {'type': 'A', 'ttl': 3600, 'values': ['10.2.3.7']}),
        ):
            record = Record.new(expected, name, data)
            expected.add_record(record)

        changes = expected.changes(got, SimpleProvider())
        self.assertEqual([], changes)

    def test_populate_normal_sub2(self):
        got = Zone('blah-asdf.subtest.com.', [])
        self.source.populate(got)
        self.assertEqual(2, len(got.records))

        expected = Zone('sub-asdf.subtest.com.', [])
        for name, data in (
            ('a1', {'type': 'A', 'ttl': 3600, 'values': ['10.2.3.5']}),
            ('a2', {'type': 'A', 'ttl': 3600, 'values': ['10.2.3.6']}),
        ):
            record = Record.new(expected, name, data)
            expected.add_record(record)

        changes = expected.changes(got, SimpleProvider())
        self.assertEqual([], changes)

    def test_populate_in_addr_arpa(self):
        got = Zone('3.2.10.in-addr.arpa.', [])
        self.source.populate(got)

        expected = Zone('3.2.10.in-addr.arpa.', [])
        for name, data in (
            ('10', {'type': 'PTR', 'ttl': 3600, 'value': 'a-ptr.example.com.'}),
            ('11', {'type': 'PTR', 'ttl': 30, 'value': 'a-ptr-2.example.com.'}),
            (
                '8',
                {
                    'type': 'PTR',
                    'ttl': 3600,
                    'values': [
                        'has-dup-def123.example.com.',
                        'has-dup-def456.example.com.',
                    ],
                },
            ),
            (
                '7',
                {
                    'type': 'PTR',
                    'ttl': 1800,
                    'value': 'some-host-abc123.example.com.',
                },
            ),
        ):
            record = Record.new(expected, name, data)
            expected.add_record(record)

        changes = expected.changes(got, SimpleProvider())
        self.assertEqual([], changes)

    def test_ignores_subs(self):
        got = Zone('example.com.', ['sub'])
        self.source.populate(got)
        # we don't see one www.sub.example.com. record b/c it's in a sub
        self.assertEqual(29, len(got.records))
