#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from unittest import TestCase

from mock import patch, call
from ovh import APIError, ResourceNotFoundError, InvalidCredential

from octodns.provider.ovh import OvhProvider
from octodns.record import Record
from octodns.zone import Zone


class TestOvhProvider(TestCase):
    api_record = []
    valid_dkim = []
    invalid_dkim = []

    valid_dkim_key = "p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCxLaG16G4SaE" \
                     "cXVdiIxTg7gKSGbHKQLm30CHib1h9FzS9nkcyvQSyQj1rMFyqC//" \
                     "tft3ohx3nvJl+bGCWxdtLYDSmir9PW54e5CTdxEh8MWRkBO3StF6" \
                     "QG/tAh3aTGDmkqhIJGLb87iHvpmVKqURmEUzJPv5KPJfWLofADI+" \
                     "q9lQIDAQAB"

    zone = Zone('unit.tests.', [])
    expected = set()

    # A, subdomain=''
    api_record.append({
        'fieldType': 'A',
        'ttl': 100,
        'target': '1.2.3.4',
        'subDomain': '',
        'id': 1
    })
    expected.add(Record.new(zone, '', {
        'ttl': 100,
        'type': 'A',
        'value': '1.2.3.4',
    }))

    # A, subdomain='sub
    api_record.append({
        'fieldType': 'A',
        'ttl': 200,
        'target': '1.2.3.4',
        'subDomain': 'sub',
        'id': 2
    })
    expected.add(Record.new(zone, 'sub', {
        'ttl': 200,
        'type': 'A',
        'value': '1.2.3.4',
    }))

    # CNAME
    api_record.append({
        'fieldType': 'CNAME',
        'ttl': 300,
        'target': 'unit.tests.',
        'subDomain': 'www2',
        'id': 3
    })
    expected.add(Record.new(zone, 'www2', {
        'ttl': 300,
        'type': 'CNAME',
        'value': 'unit.tests.',
    }))

    # MX
    api_record.append({
        'fieldType': 'MX',
        'ttl': 400,
        'target': '10 mx1.unit.tests.',
        'subDomain': '',
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

    # NAPTR
    api_record.append({
        'fieldType': 'NAPTR',
        'ttl': 500,
        'target': '10 100 "S" "SIP+D2U" "!^.*$!sip:info@bar.example.com!" .',
        'subDomain': 'naptr',
        'id': 5
    })
    expected.add(Record.new(zone, 'naptr', {
        'ttl': 500,
        'type': 'NAPTR',
        'values': [{
            'flags': 'S',
            'order': 10,
            'preference': 100,
            'regexp': '!^.*$!sip:info@bar.example.com!',
            'replacement': '.',
            'service': 'SIP+D2U',
        }]
    }))

    # NS
    api_record.append({
        'fieldType': 'NS',
        'ttl': 600,
        'target': 'ns1.unit.tests.',
        'subDomain': '',
        'id': 6
    })
    api_record.append({
        'fieldType': 'NS',
        'ttl': 600,
        'target': 'ns2.unit.tests.',
        'subDomain': '',
        'id': 7
    })
    expected.add(Record.new(zone, '', {
        'ttl': 600,
        'type': 'NS',
        'values': ['ns1.unit.tests.', 'ns2.unit.tests.'],
    }))

    # NS with sub
    api_record.append({
        'fieldType': 'NS',
        'ttl': 700,
        'target': 'ns3.unit.tests.',
        'subDomain': 'www3',
        'id': 8
    })
    api_record.append({
        'fieldType': 'NS',
        'ttl': 700,
        'target': 'ns4.unit.tests.',
        'subDomain': 'www3',
        'id': 9
    })
    expected.add(Record.new(zone, 'www3', {
        'ttl': 700,
        'type': 'NS',
        'values': ['ns3.unit.tests.', 'ns4.unit.tests.'],
    }))

    api_record.append({
        'fieldType': 'SRV',
        'ttl': 800,
        'target': '10 20 30 foo-1.unit.tests.',
        'subDomain': '_srv._tcp',
        'id': 10
    })
    api_record.append({
        'fieldType': 'SRV',
        'ttl': 800,
        'target': '40 50 60 foo-2.unit.tests.',
        'subDomain': '_srv._tcp',
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

    # PTR
    api_record.append({
        'fieldType': 'PTR',
        'ttl': 900,
        'target': 'unit.tests.',
        'subDomain': '4',
        'id': 12
    })
    expected.add(Record.new(zone, '4', {
        'ttl': 900,
        'type': 'PTR',
        'value': 'unit.tests.'
    }))

    # SPF
    api_record.append({
        'fieldType': 'SPF',
        'ttl': 1000,
        'target': 'v=spf1 include:unit.texts.redirect ~all',
        'subDomain': '',
        'id': 13
    })
    expected.add(Record.new(zone, '', {
        'ttl': 1000,
        'type': 'SPF',
        'value': 'v=spf1 include:unit.texts.redirect ~all'
    }))

    # SSHFP
    api_record.append({
        'fieldType': 'SSHFP',
        'ttl': 1100,
        'target': '1 1 bf6b6825d2977c511a475bbefb88aad54a92ac73 ',
        'subDomain': '',
        'id': 14
    })
    expected.add(Record.new(zone, '', {
        'ttl': 1100,
        'type': 'SSHFP',
        'value': {
            'algorithm': 1,
            'fingerprint': 'bf6b6825d2977c511a475bbefb88aad54a92ac73',
            'fingerprint_type': 1
        }
    }))

    # AAAA
    api_record.append({
        'fieldType': 'AAAA',
        'ttl': 1200,
        'target': '1:1ec:1::1',
        'subDomain': '',
        'id': 15
    })
    expected.add(Record.new(zone, '', {
        'ttl': 200,
        'type': 'AAAA',
        'value': '1:1ec:1::1',
    }))

    # DKIM
    api_record.append({
        'fieldType': 'DKIM',
        'ttl': 1300,
        'target': valid_dkim_key,
        'subDomain': 'dkim',
        'id': 16
    })
    expected.add(Record.new(zone, 'dkim', {
        'ttl': 1300,
        'type': 'TXT',
        'value': valid_dkim_key,
    }))

    # TXT
    api_record.append({
        'fieldType': 'TXT',
        'ttl': 1400,
        'target': 'TXT text',
        'subDomain': 'txt',
        'id': 17
    })
    expected.add(Record.new(zone, 'txt', {
        'ttl': 1400,
        'type': 'TXT',
        'value': 'TXT text',
    }))

    # LOC
    # We do not have associated record for LOC, as it's not managed
    api_record.append({
        'fieldType': 'LOC',
        'ttl': 1500,
        'target': '1 1 1 N 1 1 1 E 1m 1m',
        'subDomain': '',
        'id': 18
    })

    valid_dkim = [valid_dkim_key,
                  'v=DKIM1 \\; %s' % valid_dkim_key,
                  'h=sha256 \\; %s' % valid_dkim_key,
                  'h=sha1 \\; %s' % valid_dkim_key,
                  's=* \\; %s' % valid_dkim_key,
                  's=email \\; %s' % valid_dkim_key,
                  't=y \\; %s' % valid_dkim_key,
                  't=s \\; %s' % valid_dkim_key,
                  'k=rsa \\; %s' % valid_dkim_key,
                  'n=notes \\; %s' % valid_dkim_key,
                  'g=granularity \\; %s' % valid_dkim_key,
                  ]
    invalid_dkim = ['p=%invalid%',  # Invalid public key
                    'v=DKIM1',  # Missing public key
                    'v=DKIM2 \\; %s' % valid_dkim_key,  # Invalid version
                    'h=sha512 \\; %s' % valid_dkim_key,  # Invalid hash algo
                    's=fake \\; %s' % valid_dkim_key,  # Invalid selector
                    't=fake \\; %s' % valid_dkim_key,  # Invalid flag
                    'u=invalid \\; %s' % valid_dkim_key,  # Invalid key
                    ]

    @patch('ovh.Client')
    def test_populate(self, client_mock):
        provider = OvhProvider('test', 'endpoint', 'application_key',
                               'application_secret', 'consumer_key')

        with patch.object(provider._client, 'get') as get_mock:
            zone = Zone('unit.tests.', [])
            get_mock.side_effect = ResourceNotFoundError('boom')
            with self.assertRaises(APIError) as ctx:
                provider.populate(zone)
            self.assertEquals(get_mock.side_effect, ctx.exception)

            get_mock.side_effect = InvalidCredential('boom')
            with self.assertRaises(APIError) as ctx:
                provider.populate(zone)
            self.assertEquals(get_mock.side_effect, ctx.exception)

            zone = Zone('unit.tests.', [])
            get_mock.side_effect = ResourceNotFoundError('This service does '
                                                         'not exist')
            exists = provider.populate(zone)
            self.assertEquals(set(), zone.records)
            self.assertFalse(exists)

            zone = Zone('unit.tests.', [])
            get_returns = [[record['id'] for record in self.api_record]]
            get_returns += self.api_record
            get_mock.side_effect = get_returns
            exists = provider.populate(zone)
            self.assertEquals(self.expected, zone.records)
            self.assertTrue(exists)

    @patch('ovh.Client')
    def test_is_valid_dkim(self, client_mock):
        """Test _is_valid_dkim"""
        provider = OvhProvider('test', 'endpoint', 'application_key',
                               'application_secret', 'consumer_key')
        for dkim in self.valid_dkim:
            self.assertTrue(provider._is_valid_dkim(dkim))
        for dkim in self.invalid_dkim:
            self.assertFalse(provider._is_valid_dkim(dkim))

    @patch('ovh.Client')
    def test_apply(self, client_mock):
        provider = OvhProvider('test', 'endpoint', 'application_key',
                               'application_secret', 'consumer_key')

        desired = Zone('unit.tests.', [])

        for r in self.expected:
            desired.add_record(r)

        with patch.object(provider._client, 'post') as get_mock:
            plan = provider.plan(desired)
            get_mock.side_effect = APIError('boom')
            with self.assertRaises(APIError) as ctx:
                provider.apply(plan)
            self.assertEquals(get_mock.side_effect, ctx.exception)

        # Records get by API call
        with patch.object(provider._client, 'get') as get_mock:
            get_returns = [
                [1, 2, 3, 4],
                {'fieldType': 'A', 'ttl': 600, 'target': '5.6.7.8',
                 'subDomain': '', 'id': 100},
                {'fieldType': 'A', 'ttl': 600, 'target': '5.6.7.8',
                 'subDomain': 'fake', 'id': 101},
                {'fieldType': 'TXT', 'ttl': 600, 'target': 'fake txt record',
                 'subDomain': 'txt', 'id': 102},
                {'fieldType': 'DKIM', 'ttl': 600,
                 'target': 'v=DKIM1; %s' % self.valid_dkim_key,
                 'subDomain': 'dkim', 'id': 103}
            ]
            get_mock.side_effect = get_returns

            plan = provider.plan(desired)

            with patch.object(provider._client, 'post') as post_mock, \
                    patch.object(provider._client, 'delete') as delete_mock:
                get_mock.side_effect = [[100], [101], [102], [103]]
                provider.apply(plan)
                wanted_calls = [
                    call(u'/domain/zone/unit.tests/record', fieldType=u'TXT',
                         subDomain='txt', target=u'TXT text', ttl=1400),
                    call(u'/domain/zone/unit.tests/record', fieldType=u'DKIM',
                         subDomain='dkim', target=self.valid_dkim_key,
                         ttl=1300),
                    call(u'/domain/zone/unit.tests/record', fieldType=u'A',
                         subDomain=u'', target=u'1.2.3.4', ttl=100),
                    call(u'/domain/zone/unit.tests/record', fieldType=u'SRV',
                         subDomain='_srv._tcp',
                         target=u'10 20 30 foo-1.unit.tests.', ttl=800),
                    call(u'/domain/zone/unit.tests/record', fieldType=u'SRV',
                         subDomain='_srv._tcp',
                         target=u'40 50 60 foo-2.unit.tests.', ttl=800),
                    call(u'/domain/zone/unit.tests/record', fieldType=u'PTR',
                         subDomain='4', target=u'unit.tests.', ttl=900),
                    call(u'/domain/zone/unit.tests/record', fieldType=u'NS',
                         subDomain='www3', target=u'ns3.unit.tests.', ttl=700),
                    call(u'/domain/zone/unit.tests/record', fieldType=u'NS',
                         subDomain='www3', target=u'ns4.unit.tests.', ttl=700),
                    call(u'/domain/zone/unit.tests/record',
                         fieldType=u'SSHFP', subDomain=u'', ttl=1100,
                         target=u'1 1 bf6b6825d2977c511a475bbefb88a'
                                   u'ad54'
                                   u'a92ac73',
                         ),
                    call(u'/domain/zone/unit.tests/record', fieldType=u'AAAA',
                         subDomain=u'', target=u'1:1ec:1::1', ttl=200),
                    call(u'/domain/zone/unit.tests/record', fieldType=u'MX',
                         subDomain=u'', target=u'10 mx1.unit.tests.', ttl=400),
                    call(u'/domain/zone/unit.tests/record', fieldType=u'CNAME',
                         subDomain='www2', target=u'unit.tests.', ttl=300),
                    call(u'/domain/zone/unit.tests/record', fieldType=u'SPF',
                         subDomain=u'', ttl=1000,
                         target=u'v=spf1 include:unit.texts.'
                                u'redirect ~all',
                         ),
                    call(u'/domain/zone/unit.tests/record', fieldType=u'A',
                         subDomain='sub', target=u'1.2.3.4', ttl=200),
                    call(u'/domain/zone/unit.tests/record', fieldType=u'NAPTR',
                         subDomain='naptr', ttl=500,
                         target=u'10 100 "S" "SIP+D2U" "!^.*$!sip:'
                                u'info@bar'
                                u'.example.com!" .'
                         ),
                    call(u'/domain/zone/unit.tests/refresh')]

                post_mock.assert_has_calls(wanted_calls)

                # Get for delete calls
                wanted_get_calls = [
                    call(u'/domain/zone/unit.tests/record', fieldType=u'TXT',
                         subDomain='txt'),
                    call(u'/domain/zone/unit.tests/record', fieldType=u'DKIM',
                         subDomain='dkim'),
                    call(u'/domain/zone/unit.tests/record', fieldType=u'A',
                         subDomain=u''),
                    call(u'/domain/zone/unit.tests/record', fieldType=u'A',
                         subDomain='fake')]
                get_mock.assert_has_calls(wanted_get_calls)
                # 4 delete calls for update and delete
                delete_mock.assert_has_calls(
                    [call(u'/domain/zone/unit.tests/record/100'),
                     call(u'/domain/zone/unit.tests/record/101'),
                     call(u'/domain/zone/unit.tests/record/102'),
                     call(u'/domain/zone/unit.tests/record/103')])
