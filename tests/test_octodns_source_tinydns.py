#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from unittest import TestCase

from octodns.record import Record
from octodns.source.tinydns import TinyDnsFileSource
from octodns.zone import Zone

from helpers import SimpleProvider


class TestTinyDnsFileSource(TestCase):
    source = TinyDnsFileSource('test', './tests/zones/tinydns')

    def test_populate_normal(self):
        got = Zone('example.com.', [])
        self.source.populate(got)
        self.assertEquals(17, len(got.records))

        expected = Zone('example.com.', [])
        for name, data in (
            ('', {
                'type': 'A',
                'ttl': 30,
                'values': ['10.2.3.4', '10.2.3.5'],
            }),
            ('', {
                'type': 'NS',
                'ttl': 3600,
                'values': ['ns1.ns.com.', 'ns2.ns.com.'],
            }),
            ('sub', {
                'type': 'NS',
                'ttl': 30,
                'values': ['ns1.ns.com.', 'ns2.ns.com.'],
            }),
            ('www', {
                'type': 'A',
                'ttl': 3600,
                'value': '10.2.3.6',
            }),
            ('cname', {
                'type': 'CNAME',
                'ttl': 3600,
                'value': 'www.example.com.',
            }),
            ('some-host-abc123', {
                'type': 'A',
                'ttl': 1800,
                'value': '10.2.3.7',
            }),
            ('has-dup-def123', {
                'type': 'A',
                'ttl': 3600,
                'value': '10.2.3.8',
            }),
            ('www.sub', {
                'type': 'A',
                'ttl': 3600,
                'value': '1.2.3.4',
            }),
            ('has-dup-def456', {
                'type': 'A',
                'ttl': 3600,
                'value': '10.2.3.8',
            }),
            ('', {
                'type': 'MX',
                'ttl': 3600,
                'values': [{
                    'preference': 10,
                    'exchange': 'smtp-1-host.example.com.',
                }, {
                    'preference': 20,
                    'exchange': 'smtp-2-host.example.com.',
                }]
            }),
            ('smtp', {
                'type': 'MX',
                'ttl': 1800,
                'values': [{
                    'preference': 30,
                    'exchange': 'smtp-1-host.example.com.',
                }, {
                    'preference': 40,
                    'exchange': 'smtp-2-host.example.com.',
                }]
            }),
            ('', {
                'type': 'TXT',
                'ttl': 300,
                'value': 'test TXT',
            }),
            ('colon', {
                'type': 'TXT',
                'ttl': 300,
                'value': 'test : TXT',
            }),
            ('nottl', {
                'type': 'TXT',
                'ttl': 3600,
                'value': 'nottl test TXT',
            }),
            ('ipv6-3', {
                'type': 'AAAA',
                'ttl': 300,
                'value': '2a02:1348:017c:d5d0:0024:19ff:fef3:5742',
            }),
            ('ipv6-6', {
                'type': 'AAAA',
                'ttl': 3600,
                'value': '2a02:1348:017c:d5d0:0024:19ff:fef3:5743',
            }),
            ('semicolon', {
                'type': 'TXT',
                'ttl': 300,
                'value': 'v=DKIM1\\; k=rsa\\; p=blah',
            }),
        ):
            record = Record.new(expected, name, data)
            expected.add_record(record)

        changes = expected.changes(got, SimpleProvider())
        self.assertEquals([], changes)

    def test_populate_normal_sub1(self):
        got = Zone('asdf.subtest.com.', [])
        self.source.populate(got)
        self.assertEquals(1, len(got.records))

        expected = Zone('asdf.subtest.com.', [])
        for name, data in (
            ('a3', {
                'type': 'A',
                'ttl': 3600,
                'values': ['10.2.3.7'],
            }),
        ):
            record = Record.new(expected, name, data)
            expected.add_record(record)

        changes = expected.changes(got, SimpleProvider())
        self.assertEquals([], changes)

    def test_populate_normal_sub2(self):
        got = Zone('blah-asdf.subtest.com.', [])
        self.source.populate(got)
        self.assertEquals(2, len(got.records))

        expected = Zone('sub-asdf.subtest.com.', [])
        for name, data in (
            ('a1', {
                'type': 'A',
                'ttl': 3600,
                'values': ['10.2.3.5'],
            }),
            ('a2', {
                'type': 'A',
                'ttl': 3600,
                'values': ['10.2.3.6'],
            }),
        ):
            record = Record.new(expected, name, data)
            expected.add_record(record)

        changes = expected.changes(got, SimpleProvider())
        self.assertEquals([], changes)

    def test_populate_in_addr_arpa(self):

        got = Zone('3.2.10.in-addr.arpa.', [])
        self.source.populate(got)

        expected = Zone('3.2.10.in-addr.arpa.', [])
        for name, data in (
            ('10', {
                'type': 'PTR',
                'ttl': 3600,
                'value': 'a-ptr.example.com.'
            }),
            ('11', {
                'type': 'PTR',
                'ttl': 30,
                'value': 'a-ptr-2.example.com.'
            }),
            ('8', {
                'type': 'PTR',
                'ttl': 3600,
                'value': 'has-dup-def123.example.com.'
            }),
            ('7', {
                'type': 'PTR',
                'ttl': 1800,
                'value': 'some-host-abc123.example.com.'
            }),
        ):
            record = Record.new(expected, name, data)
            expected.add_record(record)

        changes = expected.changes(got, SimpleProvider())
        self.assertEquals([], changes)

    def test_ignores_subs(self):
        got = Zone('example.com.', ['sub'])
        self.source.populate(got)
        self.assertEquals(16, len(got.records))
