#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from unittest import TestCase
from six import text_type

import requests_mock

from octodns.provider.selectel import SelectelProvider
from octodns.record import Record, Update
from octodns.zone import Zone


class TestSelectelProvider(TestCase):
    API_URL = 'https://api.selectel.ru/domains/v1'

    api_record = []

    zone = Zone('unit.tests.', [])
    expected = set()

    domain = [{"name": "unit.tests", "id": 100000}]

    # A, subdomain=''
    api_record.append({
        'type': 'A',
        'ttl': 100,
        'content': '1.2.3.4',
        'name': 'unit.tests',
        'id': 1
    })
    expected.add(Record.new(zone, '', {
        'ttl': 100,
        'type': 'A',
        'value': '1.2.3.4',
    }))

    # A, subdomain='sub'
    api_record.append({
        'type': 'A',
        'ttl': 200,
        'content': '1.2.3.4',
        'name': 'sub.unit.tests',
        'id': 2
    })
    expected.add(Record.new(zone, 'sub', {
        'ttl': 200,
        'type': 'A',
        'value': '1.2.3.4',
    }))

    # CNAME
    api_record.append({
        'type': 'CNAME',
        'ttl': 300,
        'content': 'unit.tests',
        'name': 'www2.unit.tests',
        'id': 3
    })
    expected.add(Record.new(zone, 'www2', {
        'ttl': 300,
        'type': 'CNAME',
        'value': 'unit.tests.',
    }))

    # MX
    api_record.append({
        'type': 'MX',
        'ttl': 400,
        'content': 'mx1.unit.tests',
        'priority': 10,
        'name': 'unit.tests',
        'id': 4
    })
    expected.add(Record.new(zone, '', {
        'ttl': 400,
        'type': 'MX',
        'values': [{
            'preference': 10,
            'exchange': 'mx1.unit.tests.',
        }]
    }))

    # NS
    api_record.append({
        'type': 'NS',
        'ttl': 600,
        'content': 'ns1.unit.tests',
        'name': 'unit.tests.',
        'id': 6
    })
    api_record.append({
        'type': 'NS',
        'ttl': 600,
        'content': 'ns2.unit.tests',
        'name': 'unit.tests',
        'id': 7
    })
    expected.add(Record.new(zone, '', {
        'ttl': 600,
        'type': 'NS',
        'values': ['ns1.unit.tests.', 'ns2.unit.tests.'],
    }))

    # NS with sub
    api_record.append({
        'type': 'NS',
        'ttl': 700,
        'content': 'ns3.unit.tests',
        'name': 'www3.unit.tests',
        'id': 8
    })
    api_record.append({
        'type': 'NS',
        'ttl': 700,
        'content': 'ns4.unit.tests',
        'name': 'www3.unit.tests',
        'id': 9
    })
    expected.add(Record.new(zone, 'www3', {
        'ttl': 700,
        'type': 'NS',
        'values': ['ns3.unit.tests.', 'ns4.unit.tests.'],
    }))

    # SRV
    api_record.append({
        'type': 'SRV',
        'ttl': 800,
        'target': 'foo-1.unit.tests',
        'weight': 20,
        'priority': 10,
        'port': 30,
        'id': 10,
        'name': '_srv._tcp.unit.tests'
    })
    api_record.append({
        'type': 'SRV',
        'ttl': 800,
        'target': 'foo-2.unit.tests',
        'name': '_srv._tcp.unit.tests',
        'weight': 50,
        'priority': 40,
        'port': 60,
        'id': 11
    })
    expected.add(Record.new(zone, '_srv._tcp', {
        'ttl': 800,
        'type': 'SRV',
        'values': [{
            'priority': 10,
            'weight': 20,
            'port': 30,
            'target': 'foo-1.unit.tests.',
        }, {
            'priority': 40,
            'weight': 50,
            'port': 60,
            'target': 'foo-2.unit.tests.',
        }]
    }))

    # AAAA
    aaaa_record = {
        'type': 'AAAA',
        'ttl': 200,
        'content': '1:1ec:1::1',
        'name': 'unit.tests',
        'id': 15
    }
    api_record.append(aaaa_record)
    expected.add(Record.new(zone, '', {
        'ttl': 200,
        'type': 'AAAA',
        'value': '1:1ec:1::1',
    }))

    # TXT
    api_record.append({
        'type': 'TXT',
        'ttl': 300,
        'content': 'little text',
        'name': 'text.unit.tests',
        'id': 16
    })
    expected.add(Record.new(zone, 'text', {
        'ttl': 200,
        'type': 'TXT',
        'value': 'little text',
    }))

    @requests_mock.Mocker()
    def test_populate(self, fake_http):
        zone = Zone('unit.tests.', [])
        fake_http.get('{}/unit.tests/records/'.format(self.API_URL),
                      json=self.api_record)
        fake_http.get('{}/'.format(self.API_URL), json=self.domain)
        fake_http.head('{}/unit.tests/records/'.format(self.API_URL),
                       headers={'X-Total-Count': str(len(self.api_record))})
        fake_http.head('{}/'.format(self.API_URL),
                       headers={'X-Total-Count': str(len(self.domain))})

        provider = SelectelProvider(123, 'secret_token')
        provider.populate(zone)

        self.assertEquals(self.expected, zone.records)

    @requests_mock.Mocker()
    def test_populate_invalid_record(self, fake_http):
        more_record = self.api_record
        more_record.append({"name": "unit.tests",
                            "id": 100001,
                            "content": "support.unit.tests.",
                            "ttl": 300, "ns": "ns1.unit.tests",
                            "type": "SOA",
                            "email": "support@unit.tests"})

        zone = Zone('unit.tests.', [])
        fake_http.get('{}/unit.tests/records/'.format(self.API_URL),
                      json=more_record)
        fake_http.get('{}/'.format(self.API_URL), json=self.domain)
        fake_http.head('{}/unit.tests/records/'.format(self.API_URL),
                       headers={'X-Total-Count': str(len(self.api_record))})
        fake_http.head('{}/'.format(self.API_URL),
                       headers={'X-Total-Count': str(len(self.domain))})

        zone.add_record(Record.new(self.zone, 'unsup', {
            'ttl': 200,
            'type': 'NAPTR',
            'value': {
                'order': 40,
                'preference': 70,
                'flags': 'U',
                'service': 'SIP+D2U',
                'regexp': '!^.*$!sip:info@bar.example.com!',
                'replacement': '.',
            }
        }))

        provider = SelectelProvider(123, 'secret_token')
        provider.populate(zone)

        self.assertNotEqual(self.expected, zone.records)

    @requests_mock.Mocker()
    def test_apply(self, fake_http):

        fake_http.get('{}/unit.tests/records/'.format(self.API_URL),
                      json=list())
        fake_http.get('{}/'.format(self.API_URL), json=self.domain)
        fake_http.head('{}/unit.tests/records/'.format(self.API_URL),
                       headers={'X-Total-Count': '0'})
        fake_http.head('{}/'.format(self.API_URL),
                       headers={'X-Total-Count': str(len(self.domain))})
        fake_http.post('{}/100000/records/'.format(self.API_URL), json=list())

        provider = SelectelProvider(123, 'test_token')

        zone = Zone('unit.tests.', [])

        for record in self.expected:
            zone.add_record(record)

        plan = provider.plan(zone)
        self.assertEquals(8, len(plan.changes))
        self.assertEquals(8, provider.apply(plan))

    @requests_mock.Mocker()
    def test_domain_list(self, fake_http):
        fake_http.get('{}/'.format(self.API_URL), json=self.domain)
        fake_http.head('{}/'.format(self.API_URL),
                       headers={'X-Total-Count': str(len(self.domain))})

        expected = {'unit.tests': self.domain[0]}
        provider = SelectelProvider(123, 'test_token')

        result = provider.domain_list()
        self.assertEquals(result, expected)

    @requests_mock.Mocker()
    def test_authentication_fail(self, fake_http):
        fake_http.get('{}/'.format(self.API_URL), status_code=401)
        fake_http.head('{}/'.format(self.API_URL),
                       headers={'X-Total-Count': str(len(self.domain))})

        with self.assertRaises(Exception) as ctx:
            SelectelProvider(123, 'fail_token')
        self.assertEquals(text_type(ctx.exception),
                          'Authorization failed. Invalid or empty token.')

    @requests_mock.Mocker()
    def test_not_exist_domain(self, fake_http):
        fake_http.get('{}/'.format(self.API_URL), status_code=404, json='')
        fake_http.head('{}/'.format(self.API_URL),
                       headers={'X-Total-Count': str(len(self.domain))})

        fake_http.post('{}/'.format(self.API_URL),
                       json={"name": "unit.tests",
                             "create_date": 1507154178,
                             "id": 100000})
        fake_http.get('{}/unit.tests/records/'.format(self.API_URL),
                      json=list())
        fake_http.head('{}/unit.tests/records/'.format(self.API_URL),
                       headers={'X-Total-Count': str(len(self.api_record))})
        fake_http.post('{}/100000/records/'.format(self.API_URL),
                       json=list())

        provider = SelectelProvider(123, 'test_token')

        zone = Zone('unit.tests.', [])

        for record in self.expected:
            zone.add_record(record)

        plan = provider.plan(zone)
        self.assertEquals(8, len(plan.changes))
        self.assertEquals(8, provider.apply(plan))

    @requests_mock.Mocker()
    def test_delete_no_exist_record(self, fake_http):
        fake_http.get('{}/'.format(self.API_URL), json=self.domain)
        fake_http.get('{}/100000/records/'.format(self.API_URL), json=list())
        fake_http.head('{}/'.format(self.API_URL),
                       headers={'X-Total-Count': str(len(self.domain))})
        fake_http.head('{}/unit.tests/records/'.format(self.API_URL),
                       headers={'X-Total-Count': '0'})

        provider = SelectelProvider(123, 'test_token')

        zone = Zone('unit.tests.', [])

        provider.delete_record('unit.tests', 'NS', zone)

    @requests_mock.Mocker()
    def test_change_record(self, fake_http):
        exist_record = [self.aaaa_record,
                        {"content": "6.6.5.7",
                         "ttl": 100,
                         "type": "A",
                         "id": 100001,
                         "name": "delete.unit.tests"},
                        {"content": "9.8.2.1",
                         "ttl": 100,
                         "type": "A",
                         "id": 100002,
                         "name": "unit.tests"}]  # exist
        fake_http.get('{}/unit.tests/records/'.format(self.API_URL),
                      json=exist_record)
        fake_http.get('{}/'.format(self.API_URL), json=self.domain)
        fake_http.get('{}/100000/records/'.format(self.API_URL),
                      json=exist_record)
        fake_http.head('{}/unit.tests/records/'.format(self.API_URL),
                       headers={'X-Total-Count': str(len(exist_record))})
        fake_http.head('{}/'.format(self.API_URL),
                       headers={'X-Total-Count': str(len(self.domain))})
        fake_http.head('{}/100000/records/'.format(self.API_URL),
                       headers={'X-Total-Count': str(len(exist_record))})
        fake_http.post('{}/100000/records/'.format(self.API_URL),
                       json=list())
        fake_http.delete('{}/100000/records/100001'.format(self.API_URL),
                         text="")
        fake_http.delete('{}/100000/records/100002'.format(self.API_URL),
                         text="")

        provider = SelectelProvider(123, 'test_token')

        zone = Zone('unit.tests.', [])

        for record in self.expected:
            zone.add_record(record)

        plan = provider.plan(zone)
        self.assertEquals(8, len(plan.changes))
        self.assertEquals(8, provider.apply(plan))

    @requests_mock.Mocker()
    def test_include_change_returns_false(self, fake_http):
        fake_http.get('{}/'.format(self.API_URL), json=self.domain)
        fake_http.head('{}/'.format(self.API_URL),
                       headers={'X-Total-Count': str(len(self.domain))})
        provider = SelectelProvider(123, 'test_token')
        zone = Zone('unit.tests.', [])

        exist_record = Record.new(zone, '', {
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2']
        })
        new = Record.new(zone, '', {
            'ttl': 10,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2']
        })
        change = Update(exist_record, new)

        include_change = provider._include_change(change)

        self.assertFalse(include_change)
