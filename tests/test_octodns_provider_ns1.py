#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from mock import Mock, call, patch
from nsone.rest.errors import AuthException, RateLimitException, \
    ResourceException
from unittest import TestCase

from octodns.record import Delete, Record, Update
from octodns.provider.ns1 import Ns1Provider
from octodns.zone import Zone


class DummyZone(object):

    def __init__(self, records):
        self.data = {
            'records': records
        }


class TestNs1Provider(TestCase):
    zone = Zone('unit.tests.', [])
    expected = set()
    expected.add(Record.new(zone, '', {
        'ttl': 32,
        'type': 'A',
        'value': '1.2.3.4',
        'meta': {},
    }))
    expected.add(Record.new(zone, 'foo', {
        'ttl': 33,
        'type': 'A',
        'values': ['1.2.3.4', '1.2.3.5'],
        'meta': {},
    }))
    expected.add(Record.new(zone, 'geo', {
        'ttl': 34,
        'type': 'A',
        'values': ['101.102.103.104', '101.102.103.105'],
        'geo': {'NA-US-NY': ['201.202.203.204']},
        'meta': {},
    }))
    expected.add(Record.new(zone, 'cname', {
        'ttl': 34,
        'type': 'CNAME',
        'value': 'foo.unit.tests.',
    }))
    expected.add(Record.new(zone, '', {
        'ttl': 35,
        'type': 'MX',
        'values': [{
            'preference': 10,
            'exchange': 'mx1.unit.tests.',
        }, {
            'preference': 20,
            'exchange': 'mx2.unit.tests.',
        }]
    }))
    expected.add(Record.new(zone, 'naptr', {
        'ttl': 36,
        'type': 'NAPTR',
        'values': [{
            'flags': 'U',
            'order': 100,
            'preference': 100,
            'regexp': '!^.*$!sip:info@bar.example.com!',
            'replacement': '.',
            'service': 'SIP+D2U',
        }, {
            'flags': 'S',
            'order': 10,
            'preference': 100,
            'regexp': '!^.*$!sip:info@bar.example.com!',
            'replacement': '.',
            'service': 'SIP+D2U',
        }]
    }))
    expected.add(Record.new(zone, '', {
        'ttl': 37,
        'type': 'NS',
        'values': ['ns1.unit.tests.', 'ns2.unit.tests.'],
    }))
    expected.add(Record.new(zone, '_srv._tcp', {
        'ttl': 38,
        'type': 'SRV',
        'values': [{
            'priority': 10,
            'weight': 20,
            'port': 30,
            'target': 'foo-1.unit.tests.',
        }, {
            'priority': 12,
            'weight': 30,
            'port': 30,
            'target': 'foo-2.unit.tests.',
        }]
    }))
    expected.add(Record.new(zone, 'sub', {
        'ttl': 39,
        'type': 'NS',
        'values': ['ns3.unit.tests.', 'ns4.unit.tests.'],
    }))
    expected.add(Record.new(zone, '', {
        'ttl': 40,
        'type': 'CAA',
        'value': {
            'flags': 0,
            'tag': 'issue',
            'value': 'ca.unit.tests',
        },
    }))

    nsone_records = [{
        'type': 'A',
        'ttl': 32,
        'short_answers': ['1.2.3.4'],
        'domain': 'unit.tests.',
    }, {
        'type': 'A',
        'ttl': 33,
        'short_answers': ['1.2.3.4', '1.2.3.5'],
        'domain': 'foo.unit.tests.',
    }, {
        'type': 'A',
        'ttl': 34,
        'short_answers': ['101.102.103.104', '101.102.103.105'],
        'domain': 'geo.unit.tests',
    }, {
        'type': 'CNAME',
        'ttl': 34,
        'short_answers': ['foo.unit.tests.'],
        'domain': 'cname.unit.tests.',
    }, {
        'type': 'MX',
        'ttl': 35,
        'short_answers': ['10 mx1.unit.tests.', '20 mx2.unit.tests.'],
        'domain': 'unit.tests.',
    }, {
        'type': 'NAPTR',
        'ttl': 36,
        'short_answers': [
            '10 100 S SIP+D2U !^.*$!sip:info@bar.example.com! .',
            '100 100 U SIP+D2U !^.*$!sip:info@bar.example.com! .'
        ],
        'domain': 'naptr.unit.tests.',
    }, {
        'type': 'NS',
        'ttl': 37,
        'short_answers': ['ns1.unit.tests.', 'ns2.unit.tests.'],
        'domain': 'unit.tests.',
    }, {
        'type': 'SRV',
        'ttl': 38,
        'short_answers': ['12 30 30 foo-2.unit.tests.',
                          '10 20 30 foo-1.unit.tests.'],
        'domain': '_srv._tcp.unit.tests.',
    }, {
        'type': 'NS',
        'ttl': 39,
        'short_answers': ['ns3.unit.tests.', 'ns4.unit.tests.'],
        'domain': 'sub.unit.tests.',
    }, {
        'type': 'CAA',
        'ttl': 40,
        'short_answers': ['0 issue ca.unit.tests'],
        'domain': 'unit.tests.',
    }]

    @patch('nsone.NSONE.loadZone')
    def test_populate(self, load_mock):
        provider = Ns1Provider('test', 'api-key')

        # Bad auth
        load_mock.side_effect = AuthException('unauthorized')
        zone = Zone('unit.tests.', [])
        with self.assertRaises(AuthException) as ctx:
            provider.populate(zone)
        self.assertEquals(load_mock.side_effect, ctx.exception)

        # General error
        load_mock.reset_mock()
        load_mock.side_effect = ResourceException('boom')
        zone = Zone('unit.tests.', [])
        with self.assertRaises(ResourceException) as ctx:
            provider.populate(zone)
        self.assertEquals(load_mock.side_effect, ctx.exception)
        self.assertEquals(('unit.tests',), load_mock.call_args[0])

        # Non-existant zone doesn't populate anything
        load_mock.reset_mock()
        load_mock.side_effect = \
            ResourceException('server error: zone not found')
        zone = Zone('unit.tests.', [])
        exists = provider.populate(zone)
        self.assertEquals(set(), zone.records)
        self.assertEquals(('unit.tests',), load_mock.call_args[0])
        self.assertFalse(exists)

        # Existing zone w/o records
        load_mock.reset_mock()
        nsone_zone = DummyZone([])
        load_mock.side_effect = [nsone_zone]
        zone_search = Mock()
        zone_search.return_value = [
            {
                "domain": "geo.unit.tests",
                "zone": "unit.tests",
                "type": "A",
                "answers": [
                    {'answer': ['1.1.1.1'], 'meta': {}},
                    {'answer': ['1.2.3.4'],
                     'meta': {'ca_province': ['ON']}},
                    {'answer': ['2.3.4.5'], 'meta': {'us_state': ['NY']}},
                    {'answer': ['3.4.5.6'], 'meta': {'country': ['US']}},
                    {'answer': ['4.5.6.7'],
                     'meta': {'iso_region_code': ['NA-US-WA']}},
                ],
                'ttl': 34,
            },
        ]
        nsone_zone.search = zone_search
        zone = Zone('unit.tests.', [])
        provider.populate(zone)
        self.assertEquals(1, len(zone.records))
        self.assertEquals(('unit.tests',), load_mock.call_args[0])

        # Existing zone w/records
        load_mock.reset_mock()
        nsone_zone = DummyZone(self.nsone_records)
        load_mock.side_effect = [nsone_zone]
        zone_search = Mock()
        zone_search.return_value = [
            {
                "domain": "geo.unit.tests",
                "zone": "unit.tests",
                "type": "A",
                "answers": [
                    {'answer': ['1.1.1.1'], 'meta': {}},
                    {'answer': ['1.2.3.4'],
                     'meta': {'ca_province': ['ON']}},
                    {'answer': ['2.3.4.5'], 'meta': {'us_state': ['NY']}},
                    {'answer': ['3.4.5.6'], 'meta': {'country': ['US']}},
                    {'answer': ['4.5.6.7'],
                     'meta': {'iso_region_code': ['NA-US-WA']}},
                ],
                'ttl': 34,
            },
        ]
        nsone_zone.search = zone_search
        zone = Zone('unit.tests.', [])
        provider.populate(zone)
        self.assertEquals(self.expected, zone.records)
        self.assertEquals(('unit.tests',), load_mock.call_args[0])

        # Test skipping unsupported record type
        load_mock.reset_mock()
        nsone_zone = DummyZone(self.nsone_records + [{
            'type': 'UNSUPPORTED',
            'ttl': 42,
            'short_answers': ['unsupported'],
            'domain': 'unsupported.unit.tests.',
        }])
        load_mock.side_effect = [nsone_zone]
        zone_search = Mock()
        zone_search.return_value = [
            {
                "domain": "geo.unit.tests",
                "zone": "unit.tests",
                "type": "A",
                "answers": [
                    {'answer': ['1.1.1.1'], 'meta': {}},
                    {'answer': ['1.2.3.4'],
                     'meta': {'ca_province': ['ON']}},
                    {'answer': ['2.3.4.5'], 'meta': {'us_state': ['NY']}},
                    {'answer': ['3.4.5.6'], 'meta': {'country': ['US']}},
                    {'answer': ['4.5.6.7'],
                     'meta': {'iso_region_code': ['NA-US-WA']}},
                ],
                'ttl': 34,
            },
        ]
        nsone_zone.search = zone_search
        zone = Zone('unit.tests.', [])
        provider.populate(zone)
        self.assertEquals(self.expected, zone.records)
        self.assertEquals(('unit.tests',), load_mock.call_args[0])

    @patch('nsone.NSONE.createZone')
    @patch('nsone.NSONE.loadZone')
    def test_sync(self, load_mock, create_mock):
        provider = Ns1Provider('test', 'api-key')

        desired = Zone('unit.tests.', [])
        for r in self.expected:
            desired.add_record(r)

        plan = provider.plan(desired)
        # everything except the root NS
        expected_n = len(self.expected) - 1
        self.assertEquals(expected_n, len(plan.changes))
        self.assertTrue(plan.exists)

        # Fails, general error
        load_mock.reset_mock()
        create_mock.reset_mock()
        load_mock.side_effect = ResourceException('boom')
        with self.assertRaises(ResourceException) as ctx:
            provider.apply(plan)
        self.assertEquals(load_mock.side_effect, ctx.exception)

        # Fails, bad auth
        load_mock.reset_mock()
        create_mock.reset_mock()
        load_mock.side_effect = \
            ResourceException('server error: zone not found')
        create_mock.side_effect = AuthException('unauthorized')
        with self.assertRaises(AuthException) as ctx:
            provider.apply(plan)
        self.assertEquals(create_mock.side_effect, ctx.exception)

        # non-existant zone, create
        load_mock.reset_mock()
        create_mock.reset_mock()
        load_mock.side_effect = \
            ResourceException('server error: zone not found')
        # ugh, need a mock zone with a mock prop since we're using getattr, we
        # can actually control side effects on `meth` with that.
        mock_zone = Mock()
        mock_zone.add_SRV = Mock()
        mock_zone.add_SRV.side_effect = [
            RateLimitException('boo', period=0),
            None,
        ]
        create_mock.side_effect = [mock_zone]
        got_n = provider.apply(plan)
        self.assertEquals(expected_n, got_n)

        # Update & delete
        load_mock.reset_mock()
        create_mock.reset_mock()
        nsone_zone = DummyZone(self.nsone_records + [{
            'type': 'A',
            'ttl': 42,
            'short_answers': ['9.9.9.9'],
            'domain': 'delete-me.unit.tests.',
        }])
        nsone_zone.data['records'][0]['short_answers'][0] = '2.2.2.2'
        nsone_zone.loadRecord = Mock()
        zone_search = Mock()
        zone_search.return_value = [
            {
                "domain": "geo.unit.tests",
                "zone": "unit.tests",
                "type": "A",
                "answers": [
                    {'answer': ['1.1.1.1'], 'meta': {}},
                    {'answer': ['1.2.3.4'],
                     'meta': {'ca_province': ['ON']}},
                    {'answer': ['2.3.4.5'], 'meta': {'us_state': ['NY']}},
                    {'answer': ['3.4.5.6'], 'meta': {'country': ['US']}},
                    {'answer': ['4.5.6.7'],
                     'meta': {'iso_region_code': ['NA-US-WA']}},
                ],
                'ttl': 34,
            },
        ]
        nsone_zone.search = zone_search
        load_mock.side_effect = [nsone_zone, nsone_zone]
        plan = provider.plan(desired)
        self.assertEquals(3, len(plan.changes))
        self.assertIsInstance(plan.changes[0], Update)
        self.assertIsInstance(plan.changes[2], Delete)
        # ugh, we need a mock record that can be returned from loadRecord for
        # the update and delete targets, we can add our side effects to that to
        # trigger rate limit handling
        mock_record = Mock()
        mock_record.update.side_effect = [
            RateLimitException('one', period=0),
            None,
            None,
        ]
        mock_record.delete.side_effect = [
            RateLimitException('two', period=0),
            None,
            None,
        ]
        nsone_zone.loadRecord.side_effect = [mock_record, mock_record,
                                             mock_record]
        got_n = provider.apply(plan)
        self.assertEquals(3, got_n)
        nsone_zone.loadRecord.assert_has_calls([
            call('unit.tests', u'A'),
            call('geo', u'A'),
            call('delete-me', u'A'),
        ])
        mock_record.assert_has_calls([
            call.update(answers=[{'answer': [u'1.2.3.4'], 'meta': {}}],
                        filters=[],
                        ttl=32),
            call.update(answers=[{u'answer': [u'1.2.3.4'], u'meta': {}}],
                        filters=[],
                        ttl=32),
            call.update(
                answers=[
                    {u'answer': [u'101.102.103.104'], u'meta': {}},
                    {u'answer': [u'101.102.103.105'], u'meta': {}},
                    {
                        u'answer': [u'201.202.203.204'],
                        u'meta': {
                            u'iso_region_code': [u'NA-US-NY']
                        },
                    },
                ],
                filters=[
                    {u'filter': u'shuffle', u'config': {}},
                    {u'filter': u'geotarget_country', u'config': {}},
                    {u'filter': u'select_first_n', u'config': {u'N': 1}},
                ],
                ttl=34),
            call.delete(),
            call.delete()
        ])

    def test_escaping(self):
        provider = Ns1Provider('test', 'api-key')
        record = {
            'ttl': 31,
            'short_answers': ['foo; bar baz; blip']
        }
        self.assertEquals(['foo\\; bar baz\\; blip'],
                          provider._data_for_SPF('SPF', record)['values'])

        record = {
            'ttl': 31,
            'short_answers': ['no', 'foo; bar baz; blip', 'yes']
        }
        self.assertEquals(['no', 'foo\\; bar baz\\; blip', 'yes'],
                          provider._data_for_TXT('TXT', record)['values'])

        zone = Zone('unit.tests.', [])
        record = Record.new(zone, 'spf', {
            'ttl': 34,
            'type': 'SPF',
            'value': 'foo\\; bar baz\\; blip'
        })
        self.assertEquals(['foo; bar baz; blip'],
                          provider._params_for_SPF(record)['answers'])

        record = Record.new(zone, 'txt', {
            'ttl': 35,
            'type': 'TXT',
            'value': 'foo\\; bar baz\\; blip'
        })
        self.assertEquals(['foo; bar baz; blip'],
                          provider._params_for_TXT(record)['answers'])

    def test_data_for_CNAME(self):
        provider = Ns1Provider('test', 'api-key')

        # answers from nsone
        a_record = {
            'ttl': 31,
            'type': 'CNAME',
            'short_answers': ['foo.unit.tests.']
        }
        a_expected = {
            'ttl': 31,
            'type': 'CNAME',
            'value': 'foo.unit.tests.'
        }
        self.assertEqual(a_expected,
                         provider._data_for_CNAME(a_record['type'], a_record))

        # no answers from nsone
        b_record = {
            'ttl': 32,
            'type': 'CNAME',
            'short_answers': []
        }
        b_expected = {
            'ttl': 32,
            'type': 'CNAME',
            'value': None
        }
        self.assertEqual(b_expected,
                         provider._data_for_CNAME(b_record['type'], b_record))
