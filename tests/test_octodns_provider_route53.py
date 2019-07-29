#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from botocore.exceptions import ClientError
from botocore.stub import ANY, Stubber
from unittest import TestCase
from mock import patch

from octodns.record import Create, Delete, Record, Update
from octodns.provider.route53 import Route53Provider, _Route53GeoDefault, \
    _Route53DynamicValue, _Route53GeoRecord, _Route53Record, _mod_keyer, \
    _octal_replace
from octodns.zone import Zone

from helpers import GeoProvider


class DummyR53Record(object):

    def __init__(self, health_check_id):
        self.health_check_id = health_check_id


class TestOctalReplace(TestCase):

    def test_basic(self):
        for expected, s in (
            ('', ''),
            ('abc', 'abc'),
            ('123', '123'),
            ('abc123', 'abc123'),
            ('*', '\\052'),
            ('abc*', 'abc\\052'),
            ('*abc', '\\052abc'),
            ('123*', '123\\052'),
            ('*123', '\\052123'),
            ('**', '\\052\\052'),
        ):
            self.assertEquals(expected, _octal_replace(s))


dynamic_rrsets = [{
    'Name': '_octodns-default-pool.unit.tests.',
    'ResourceRecords': [{'Value': '1.1.2.1'},
                        {'Value': '1.1.2.2'}],
    'TTL': 60,
    'Type': 'A',
}, {
    'HealthCheckId': '76',
    'Name': '_octodns-ap-southeast-1-value.unit.tests.',
    'ResourceRecords': [{'Value': '1.4.1.1'}],
    'SetIdentifier': 'ap-southeast-1-000',
    'TTL': 60,
    'Type': 'A',
    'Weight': 2
}, {
    'HealthCheckId': '09',
    'Name': '_octodns-ap-southeast-1-value.unit.tests.',
    'ResourceRecords': [{'Value': '1.4.1.2'}],
    'SetIdentifier': 'ap-southeast-1-001',
    'TTL': 60,
    'Type': 'A',
    'Weight': 2
}, {
    'HealthCheckId': 'ab',
    'Name': '_octodns-eu-central-1-value.unit.tests.',
    'ResourceRecords': [{'Value': '1.3.1.1'}],
    'SetIdentifier': 'eu-central-1-000',
    'TTL': 60,
    'Type': 'A',
    'Weight': 1
}, {
    'HealthCheckId': '1e',
    'Name': '_octodns-eu-central-1-value.unit.tests.',
    'ResourceRecords': [{'Value': '1.3.1.2'}],
    'SetIdentifier': 'eu-central-1-001',
    'TTL': 60,
    'Type': 'A',
    'Weight': 1
}, {
    'HealthCheckId': '2a',
    'Name': '_octodns-us-east-1-value.unit.tests.',
    'ResourceRecords': [{'Value': '1.5.1.1'}],
    'SetIdentifier': 'us-east-1-000',
    'TTL': 60,
    'Type': 'A',
    'Weight': 1
}, {
    'HealthCheckId': '61',
    'Name': '_octodns-us-east-1-value.unit.tests.',
    'ResourceRecords': [{'Value': '1.5.1.2'}],
    'SetIdentifier': 'us-east-1-001',
    'TTL': 60,
    'Type': 'A',
    'Weight': 1,
}, {
    'AliasTarget': {'DNSName': '_octodns-default-pool.unit.tests.',
                    'EvaluateTargetHealth': True,
                    'HostedZoneId': 'Z2'},
    'Failover': 'SECONDARY',
    'Name': '_octodns-us-east-1-pool.unit.tests.',
    'SetIdentifier': 'us-east-1-Secondary-default',
    'Type': 'A'
}, {
    'AliasTarget': {
        'DNSName': '_octodns-us-east-1-value.unit.tests.',
        'EvaluateTargetHealth': True,
        'HostedZoneId': 'Z2'
    },
    'Failover': 'PRIMARY',
    'Name': '_octodns-us-east-1-pool.unit.tests.',
    'SetIdentifier': 'us-east-1-Primary',
    'Type': 'A',
}, {
    'AliasTarget': {'DNSName': '_octodns-us-east-1-pool.unit.tests.',
                    'EvaluateTargetHealth': True,
                    'HostedZoneId': 'Z2'},
    'Failover': 'SECONDARY',
    'Name': '_octodns-eu-central-1-pool.unit.tests.',
    'SetIdentifier': 'eu-central-1-Secondary-default',
    'Type': 'A'
}, {
    'AliasTarget': {
        'DNSName': '_octodns-eu-central-1-value.unit.tests.',
        'EvaluateTargetHealth': True,
        'HostedZoneId': 'Z2'
    },
    'Failover': 'PRIMARY',
    'Name': '_octodns-eu-central-1-pool.unit.tests.',
    'SetIdentifier': 'eu-central-1-Primary',
    'Type': 'A',
}, {
    'AliasTarget': {'DNSName': '_octodns-us-east-1-pool.unit.tests.',
                    'EvaluateTargetHealth': True,
                    'HostedZoneId': 'Z2'},
    'Failover': 'SECONDARY',
    'Name': '_octodns-ap-southeast-1-pool.unit.tests.',
    'SetIdentifier': 'ap-southeast-1-Secondary-default',
    'Type': 'A'
}, {
    'AliasTarget': {
        'DNSName': '_octodns-ap-southeast-1-value.unit.tests.',
        'EvaluateTargetHealth': True,
        'HostedZoneId': 'Z2'
    },
    'Failover': 'PRIMARY',
    'Name': '_octodns-ap-southeast-1-pool.unit.tests.',
    'SetIdentifier': 'ap-southeast-1-Primary',
    'Type': 'A',
}, {
    'AliasTarget': {'DNSName': '_octodns-ap-southeast-1-pool.unit.tests.',
                    'EvaluateTargetHealth': True,
                    'HostedZoneId': 'Z2'},
    'GeoLocation': {'CountryCode': 'JP'},
    'Name': 'unit.tests.',
    'SetIdentifier': '1-ap-southeast-1-AS-JP',
    'Type': 'A',
}, {
    'AliasTarget': {'DNSName': '_octodns-ap-southeast-1-pool.unit.tests.',
                    'EvaluateTargetHealth': True,
                    'HostedZoneId': 'Z2'},
    'GeoLocation': {'CountryCode': 'CN'},
    'Name': 'unit.tests.',
    'SetIdentifier': '1-ap-southeast-1-AS-CN',
    'Type': 'A',
}, {
    'AliasTarget': {'DNSName': '_octodns-eu-central-1-pool.unit.tests.',
                    'EvaluateTargetHealth': True,
                    'HostedZoneId': 'Z2'},
    'GeoLocation': {'ContinentCode': 'NA-US-FL'},
    'Name': 'unit.tests.',
    'SetIdentifier': '2-eu-central-1-NA-US-FL',
    'Type': 'A',
}, {
    'AliasTarget': {'DNSName': '_octodns-eu-central-1-pool.unit.tests.',
                    'EvaluateTargetHealth': True,
                    'HostedZoneId': 'Z2'},
    'GeoLocation': {'ContinentCode': 'EU'},
    'Name': 'unit.tests.',
    'SetIdentifier': '2-eu-central-1-EU',
    'Type': 'A',
}, {
    'AliasTarget': {'DNSName': '_octodns-us-east-1-pool.unit.tests.',
                    'EvaluateTargetHealth': True,
                    'HostedZoneId': 'Z2'},
    'GeoLocation': {'CountryCode': '*'},
    'Name': 'unit.tests.',
    'SetIdentifier': '3-us-east-1-None',
    'Type': 'A',
}]

dynamic_record_data = {
    'dynamic': {
        'pools': {
            'ap-southeast-1': {
                'fallback': 'us-east-1',
                'values': [{
                    'weight': 2, 'value': '1.4.1.1'
                }, {
                    'weight': 2, 'value': '1.4.1.2'
                }]
            },
            'eu-central-1': {
                'fallback': 'us-east-1',
                'values': [{
                    'weight': 1, 'value': '1.3.1.1'
                }, {
                    'weight': 1, 'value': '1.3.1.2'
                }],
            },
            'us-east-1': {
                'values': [{
                    'weight': 1, 'value': '1.5.1.1'
                }, {
                    'weight': 1, 'value': '1.5.1.2'
                }],
            }
        },
        'rules': [{
            'geos': ['AS-CN', 'AS-JP'],
            'pool': 'ap-southeast-1',
        }, {
            'geos': ['EU', 'NA-US-FL'],
            'pool': 'eu-central-1',
        }, {
            'pool': 'us-east-1',
        }],
    },
    'ttl': 60,
    'type': 'A',
    'values': [
        '1.1.2.1',
        '1.1.2.2',
    ],
}


class TestRoute53Provider(TestCase):
    expected = Zone('unit.tests.', [])
    for name, data in (
        ('simple',
         {'ttl': 60, 'type': 'A', 'values': ['1.2.3.4', '2.2.3.4']}),
        ('',
         {'ttl': 61, 'type': 'A', 'values': ['2.2.3.4', '3.2.3.4'],
          'geo': {
              'AF': ['4.2.3.4'],
              'NA-US': ['5.2.3.4', '6.2.3.4'],
              'NA-US-CA': ['7.2.3.4']}}),
        ('cname', {'ttl': 62, 'type': 'CNAME', 'value': 'unit.tests.'}),
        ('txt', {'ttl': 63, 'type': 'TXT', 'values': ['Hello World!',
                                                      'Goodbye World?']}),
        ('', {'ttl': 64, 'type': 'MX',
              'values': [{
                  'preference': 10,
                  'exchange': 'smtp-1.unit.tests.',
              }, {
                  'preference': 20,
                  'exchange': 'smtp-2.unit.tests.',
              }]}),
        ('naptr', {'ttl': 65, 'type': 'NAPTR',
                   'value': {
                       'order': 10,
                       'preference': 20,
                       'flags': 'U',
                       'service': 'SIP+D2U',
                       'regexp': '!^.*$!sip:info@bar.example.com!',
                       'replacement': '.',
                   }}),
        ('_srv._tcp', {'ttl': 66, 'type': 'SRV', 'value': {
            'priority': 10,
            'weight': 20,
            'port': 30,
            'target': 'cname.unit.tests.'
        }}),
        ('',
         {'ttl': 67, 'type': 'NS', 'values': ['8.2.3.4.', '9.2.3.4.']}),
        ('sub',
         {'ttl': 68, 'type': 'NS', 'values': ['5.2.3.4.', '6.2.3.4.']}),
        ('',
         {'ttl': 69, 'type': 'CAA', 'value': {
             'flags': 0,
             'tag': 'issue',
             'value': 'ca.unit.tests'
         }}),
    ):
        record = Record.new(expected, name, data)
        expected.add_record(record)

    caller_ref = '{}:A:unit.tests.:1324' \
        .format(Route53Provider.HEALTH_CHECK_VERSION)
    health_checks = [{
        'Id': '42',
        'CallerReference': caller_ref,
        'HealthCheckConfig': {
            'Type': 'HTTPS',
            'FullyQualifiedDomainName': 'unit.tests',
            'IPAddress': '4.2.3.4',
            'ResourcePath': '/_dns',
            'Type': 'HTTPS',
            'Port': 443,
            'MeasureLatency': True,
        },
        'HealthCheckVersion': 2,
    }, {
        'Id': 'ignored-also',
        'CallerReference': 'something-else',
        'HealthCheckConfig': {
            'Type': 'HTTPS',
            'FullyQualifiedDomainName': 'unit.tests',
            'IPAddress': '5.2.3.4',
            'ResourcePath': '/_dns',
            'Type': 'HTTPS',
            'Port': 443,
            'MeasureLatency': True,
        },
        'HealthCheckVersion': 42,
    }, {
        'Id': '43',
        'CallerReference': caller_ref,
        'HealthCheckConfig': {
            'Type': 'HTTPS',
            'FullyQualifiedDomainName': 'unit.tests',
            'IPAddress': '5.2.3.4',
            'ResourcePath': '/_dns',
            'Type': 'HTTPS',
            'Port': 443,
            'MeasureLatency': True,
        },
        'HealthCheckVersion': 2,
    }, {
        'Id': '44',
        'CallerReference': caller_ref,
        'HealthCheckConfig': {
            'Type': 'HTTPS',
            'FullyQualifiedDomainName': 'unit.tests',
            'IPAddress': '7.2.3.4',
            'ResourcePath': '/_dns',
            'Type': 'HTTPS',
            'Port': 443,
            'MeasureLatency': True,
        },
        'HealthCheckVersion': 2,
    }, {
        'Id': '45',
        # won't match anything based on type
        'CallerReference': caller_ref.replace(':A:', ':AAAA:'),
        'HealthCheckConfig': {
            'Type': 'HTTPS',
            'FullyQualifiedDomainName': 'unit.tests',
            'IPAddress': '7.2.3.4',
            'ResourcePath': '/_dns',
            'Type': 'HTTPS',
            'Port': 443,
            'MeasureLatency': True,
        },
        'HealthCheckVersion': 2,
    }]

    def _get_stubbed_provider(self):
        provider = Route53Provider('test', 'abc', '123')

        # Use the stubber
        stubber = Stubber(provider._conn)
        stubber.activate()

        return (provider, stubber)

    def _get_stubbed_fallback_auth_provider(self):
        provider = Route53Provider('test')

        # Use the stubber
        stubber = Stubber(provider._conn)
        stubber.activate()

        return (provider, stubber)

    def test_populate_with_fallback(self):
        provider, stubber = self._get_stubbed_fallback_auth_provider()

        got = Zone('unit.tests.', [])
        with self.assertRaises(ClientError):
            stubber.add_client_error('list_hosted_zones')
            provider.populate(got)

    def test_populate(self):
        provider, stubber = self._get_stubbed_provider()

        got = Zone('unit.tests.', [])
        with self.assertRaises(ClientError):
            stubber.add_client_error('list_hosted_zones')
            provider.populate(got)

        with self.assertRaises(ClientError):
            list_hosted_zones_resp = {
                'HostedZones': [{
                    'Name': 'unit.tests.',
                    'Id': 'z42',
                    'CallerReference': 'abc',
                }],
                'Marker': 'm',
                'IsTruncated': False,
                'MaxItems': '100',
            }
            stubber.add_response('list_hosted_zones', list_hosted_zones_resp,
                                 {})
            stubber.add_client_error('list_resource_record_sets',
                                     expected_params={'HostedZoneId': u'z42'})
            provider.populate(got)
            stubber.assert_no_pending_responses()

        # list_hosted_zones has been cached from now on so we don't have to
        # worry about stubbing it

        list_resource_record_sets_resp_p1 = {
            'ResourceRecordSets': [{
                'Name': 'simple.unit.tests.',
                'Type': 'A',
                'ResourceRecords': [{
                    'Value': '1.2.3.4',
                }, {
                    'Value': '2.2.3.4',
                }],
                'TTL': 60,
            }, {
                'Name': 'unit.tests.',
                'Type': 'A',
                'GeoLocation': {
                    'CountryCode': '*',
                },
                'ResourceRecords': [{
                    'Value': '2.2.3.4',
                }, {
                    'Value': '3.2.3.4',
                }],
                'TTL': 61,
            }, {
                'Name': 'unit.tests.',
                'Type': 'A',
                'GeoLocation': {
                    'ContinentCode': 'AF',
                },
                'ResourceRecords': [{
                    'Value': '4.2.3.4',
                }],
                'TTL': 61,
            }, {
                'Name': 'unit.tests.',
                'Type': 'A',
                'GeoLocation': {
                    'CountryCode': 'US',
                },
                'ResourceRecords': [{
                    'Value': '5.2.3.4',
                }, {
                    'Value': '6.2.3.4',
                }],
                'TTL': 61,
            }, {
                'Name': 'unit.tests.',
                'Type': 'A',
                'GeoLocation': {
                    'CountryCode': 'US',
                    'SubdivisionCode': 'CA',
                },
                'ResourceRecords': [{
                    'Value': '7.2.3.4',
                }],
                'TTL': 61,
            }],
            'IsTruncated': True,
            'NextRecordName': 'next_name',
            'NextRecordType': 'next_type',
            'MaxItems': '100',
        }
        stubber.add_response('list_resource_record_sets',
                             list_resource_record_sets_resp_p1,
                             {'HostedZoneId': 'z42'})

        list_resource_record_sets_resp_p2 = {
            'ResourceRecordSets': [{
                'Name': 'cname.unit.tests.',
                'Type': 'CNAME',
                'ResourceRecords': [{
                    'Value': 'unit.tests.',
                }],
                'TTL': 62,
            }, {
                'Name': 'txt.unit.tests.',
                'Type': 'TXT',
                'ResourceRecords': [{
                    'Value': '"Hello World!"',
                }, {
                    'Value': '"Goodbye World?"',
                }],
                'TTL': 63,
            }, {
                'Name': 'unit.tests.',
                'Type': 'MX',
                'ResourceRecords': [{
                    'Value': '10 smtp-1.unit.tests.',
                }, {
                    'Value': '20 smtp-2.unit.tests.',
                }],
                'TTL': 64,
            }, {
                'Name': 'naptr.unit.tests.',
                'Type': 'NAPTR',
                'ResourceRecords': [{
                    'Value': '10 20 "U" "SIP+D2U" '
                        '"!^.*$!sip:info@bar.example.com!" .',
                }],
                'TTL': 65,
            }, {
                'Name': '_srv._tcp.unit.tests.',
                'Type': 'SRV',
                'ResourceRecords': [{
                    'Value': '10 20 30 cname.unit.tests.',
                }],
                'TTL': 66,
            }, {
                'Name': 'unit.tests.',
                'Type': 'NS',
                'ResourceRecords': [{
                    'Value': 'ns1.unit.tests.',
                }],
                'TTL': 67,
            }, {
                'Name': 'sub.unit.tests.',
                'Type': 'NS',
                'GeoLocation': {
                    'ContinentCode': 'AF',
                },
                'ResourceRecords': [{
                    'Value': '5.2.3.4.',
                }, {
                    'Value': '6.2.3.4.',
                }],
                'TTL': 68,
            }, {
                'Name': 'soa.unit.tests.',
                'Type': 'SOA',
                'ResourceRecords': [{
                    'Value': 'ns1.unit.tests.',
                }],
                'TTL': 69,
            }, {
                'Name': 'unit.tests.',
                'Type': 'CAA',
                'ResourceRecords': [{
                    'Value': '0 issue "ca.unit.tests"',
                }],
                'TTL': 69,
            }, {
                'AliasTarget': {
                    'HostedZoneId': 'Z119WBBTVP5WFX',
                    'EvaluateTargetHealth': False,
                    'DNSName': 'unit.tests.'
                },
                'Type': 'A',
                'Name': 'alias.unit.tests.'
            }],
            'IsTruncated': False,
            'MaxItems': '100',
        }
        stubber.add_response('list_resource_record_sets',
                             list_resource_record_sets_resp_p2,
                             {'HostedZoneId': 'z42',
                              'StartRecordName': 'next_name',
                              'StartRecordType': 'next_type'})

        # Load everything
        provider.populate(got)
        # Make sure we got what we expected
        changes = self.expected.changes(got, GeoProvider())
        self.assertEquals(0, len(changes))
        stubber.assert_no_pending_responses()

        # Populate a zone that doesn't exist
        nonexistent = Zone('does.not.exist.', [])
        provider.populate(nonexistent)
        self.assertEquals(set(), nonexistent.records)

    def test_sync(self):
        provider, stubber = self._get_stubbed_provider()

        list_hosted_zones_resp = {
            'HostedZones': [{
                'Name': 'unit.tests.',
                'Id': 'z42',
                'CallerReference': 'abc',
            }],
            'Marker': 'm',
            'IsTruncated': False,
            'MaxItems': '100',
        }
        stubber.add_response('list_hosted_zones', list_hosted_zones_resp,
                             {})
        list_resource_record_sets_resp = {
            'ResourceRecordSets': [],
            'IsTruncated': False,
            'MaxItems': '100',
        }
        stubber.add_response('list_resource_record_sets',
                             list_resource_record_sets_resp,
                             {'HostedZoneId': 'z42'})

        plan = provider.plan(self.expected)
        self.assertEquals(9, len(plan.changes))
        self.assertTrue(plan.exists)
        for change in plan.changes:
            self.assertIsInstance(change, Create)
        stubber.assert_no_pending_responses()

        stubber.add_response('list_health_checks',
                             {
                                 'HealthChecks': self.health_checks,
                                 'IsTruncated': False,
                                 'MaxItems': '100',
                                 'Marker': '',
                             })
        stubber.add_response('change_resource_record_sets',
                             {'ChangeInfo': {
                                 'Id': 'id',
                                 'Status': 'PENDING',
                                 'SubmittedAt': '2017-01-29T01:02:03Z',
                             }}, {'HostedZoneId': 'z42', 'ChangeBatch': ANY})

        self.assertEquals(9, provider.apply(plan))
        stubber.assert_no_pending_responses()

        # Delete by monkey patching in a populate that includes an extra record
        def add_extra_populate(existing, target, lenient):
            for record in self.expected.records:
                existing.add_record(record)
            record = Record.new(existing, 'extra',
                                {'ttl': 99, 'type': 'A',
                                 'values': ['9.9.9.9']})
            existing.add_record(record)

        provider.populate = add_extra_populate
        change_resource_record_sets_params = {
            'ChangeBatch': {
                'Changes': [{
                    'Action': 'DELETE', 'ResourceRecordSet': {
                        'Name': 'extra.unit.tests.',
                        'ResourceRecords': [{'Value': u'9.9.9.9'}],
                        'TTL': 99,
                        'Type': 'A'
                    }}],
                u'Comment': ANY
            },
            'HostedZoneId': u'z42'
        }
        stubber.add_response('change_resource_record_sets',
                             {'ChangeInfo': {
                                 'Id': 'id',
                                 'Status': 'PENDING',
                                 'SubmittedAt': '2017-01-29T01:02:03Z',
                             }}, change_resource_record_sets_params)
        plan = provider.plan(self.expected)
        self.assertEquals(1, len(plan.changes))
        self.assertIsInstance(plan.changes[0], Delete)
        self.assertEquals(1, provider.apply(plan))
        stubber.assert_no_pending_responses()

        # Update by monkey patching in a populate that modifies the A record
        # with geos
        def mod_geo_populate(existing, target, lenient):
            for record in self.expected.records:
                if record._type != 'A' or not record.geo:
                    existing.add_record(record)
            record = Record.new(existing, '', {
                'ttl': 61,
                'type': 'A',
                'values': ['8.2.3.4', '3.2.3.4'],
                'geo': {
                    'AF': ['4.2.3.4'],
                    'NA-US': ['5.2.3.4', '6.2.3.4'],
                    'NA-US-KY': ['7.2.3.4']
                }
            })
            existing.add_record(record)

        provider.populate = mod_geo_populate
        change_resource_record_sets_params = {
            'ChangeBatch': {
                'Changes': [{
                    'Action': 'DELETE',
                    'ResourceRecordSet': {
                        'GeoLocation': {'CountryCode': 'US',
                                        'SubdivisionCode': 'KY'},
                        'HealthCheckId': u'44',
                        'Name': 'unit.tests.',
                        'ResourceRecords': [{'Value': '7.2.3.4'}],
                        'SetIdentifier': 'NA-US-KY',
                        'TTL': 61,
                        'Type': 'A'
                    }
                }, {
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'GeoLocation': {'ContinentCode': 'AF'},
                        'Name': 'unit.tests.',
                        'HealthCheckId': u'42',
                        'ResourceRecords': [{'Value': '4.2.3.4'}],
                        'SetIdentifier': 'AF',
                        'TTL': 61,
                        'Type': 'A'
                    }
                }, {
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'GeoLocation': {'CountryCode': 'US'},
                        'HealthCheckId': u'43',
                        'Name': 'unit.tests.',
                        'ResourceRecords': [{'Value': '5.2.3.4'},
                                            {'Value': '6.2.3.4'}],
                        'SetIdentifier': 'NA-US',
                        'TTL': 61,
                        'Type': 'A'
                    }
                }, {
                    'Action': 'CREATE',
                    'ResourceRecordSet': {
                        'GeoLocation': {'CountryCode': 'US',
                                        'SubdivisionCode': 'CA'},
                        'HealthCheckId': u'44',
                        'Name': 'unit.tests.',
                        'ResourceRecords': [{'Value': '7.2.3.4'}],
                        'SetIdentifier': 'NA-US-CA',
                        'TTL': 61,
                        'Type': 'A'
                    }
                }, {
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'GeoLocation': {'CountryCode': '*'},
                        'Name': 'unit.tests.',
                        'ResourceRecords': [{'Value': '2.2.3.4'},
                                            {'Value': '3.2.3.4'}],
                        'SetIdentifier': 'default',
                        'TTL': 61,
                        'Type': 'A'
                    }
                }],
                'Comment': ANY
            },
            'HostedZoneId': 'z42'
        }
        stubber.add_response('change_resource_record_sets',
                             {'ChangeInfo': {
                                 'Id': 'id',
                                 'Status': 'PENDING',
                                 'SubmittedAt': '2017-01-29T01:02:03Z',
                             }}, change_resource_record_sets_params)
        plan = provider.plan(self.expected)
        self.assertEquals(1, len(plan.changes))
        self.assertIsInstance(plan.changes[0], Update)
        self.assertEquals(1, provider.apply(plan))
        stubber.assert_no_pending_responses()

        # Update converting to non-geo by monkey patching in a populate that
        # modifies the A record with geos
        def mod_add_geo_populate(existing, target, lenient):
            for record in self.expected.records:
                if record._type != 'A' or record.geo:
                    existing.add_record(record)
            record = Record.new(existing, 'simple', {
                'ttl': 61,
                'type': 'A',
                'values': ['1.2.3.4', '2.2.3.4'],
                'geo': {
                    'OC': ['3.2.3.4', '4.2.3.4'],
                }
            })
            existing.add_record(record)

        provider.populate = mod_add_geo_populate
        change_resource_record_sets_params = {
            'ChangeBatch': {
                'Changes': [{
                    'Action': 'DELETE',
                    'ResourceRecordSet': {
                        'GeoLocation': {'ContinentCode': 'OC'},
                        'Name': 'simple.unit.tests.',
                        'ResourceRecords': [{'Value': '3.2.3.4'},
                                            {'Value': '4.2.3.4'}],
                        'SetIdentifier': 'OC',
                        'TTL': 61,
                        'Type': 'A'}
                }, {
                    'Action': 'DELETE',
                    'ResourceRecordSet': {
                        'GeoLocation': {'CountryCode': '*'},
                        'Name': 'simple.unit.tests.',
                        'ResourceRecords': [{'Value': '1.2.3.4'},
                                            {'Value': '2.2.3.4'}],
                        'SetIdentifier': 'default',
                        'TTL': 61,
                        'Type': 'A'}
                }, {
                    'Action': 'CREATE',
                    'ResourceRecordSet': {
                        'Name': 'simple.unit.tests.',
                        'ResourceRecords': [{'Value': '1.2.3.4'},
                                            {'Value': '2.2.3.4'}],
                        'TTL': 60,
                        'Type': 'A'}
                }],
                'Comment': ANY
            },
            'HostedZoneId': 'z42'
        }
        stubber.add_response('change_resource_record_sets',
                             {'ChangeInfo': {
                                 'Id': 'id',
                                 'Status': 'PENDING',
                                 'SubmittedAt': '2017-01-29T01:02:03Z',
                             }}, change_resource_record_sets_params)
        plan = provider.plan(self.expected)
        self.assertEquals(1, len(plan.changes))
        self.assertIsInstance(plan.changes[0], Update)
        self.assertEquals(1, provider.apply(plan))
        stubber.assert_no_pending_responses()

    def test_sync_create(self):
        provider, stubber = self._get_stubbed_provider()

        got = Zone('unit.tests.', [])

        list_hosted_zones_resp = {
            'HostedZones': [],
            'Marker': 'm',
            'IsTruncated': False,
            'MaxItems': '100',
        }
        stubber.add_response('list_hosted_zones', list_hosted_zones_resp,
                             {})

        plan = provider.plan(self.expected)
        self.assertEquals(9, len(plan.changes))
        self.assertFalse(plan.exists)
        for change in plan.changes:
            self.assertIsInstance(change, Create)
        stubber.assert_no_pending_responses()

        create_hosted_zone_resp = {
            'HostedZone': {
                'Name': 'unit.tests.',
                'Id': 'z42',
                'CallerReference': 'abc',
            },
            'ChangeInfo': {
                'Id': 'a12',
                'Status': 'PENDING',
                'SubmittedAt': '2017-01-29T01:02:03Z',
                'Comment': 'hrm',
            },
            'DelegationSet': {
                'Id': 'b23',
                'CallerReference': 'blip',
                'NameServers': [
                    'n12.unit.tests.',
                ],
            },
            'Location': 'us-east-1',
        }
        stubber.add_response('create_hosted_zone',
                             create_hosted_zone_resp, {
                                 'Name': got.name,
                                 'CallerReference': ANY,
                             })

        list_resource_record_sets_resp = {
            'ResourceRecordSets': [{
                'Name': 'a.unit.tests.',
                'Type': 'A',
                'GeoLocation': {
                    'ContinentCode': 'NA',
                },
                'ResourceRecords': [{
                    'Value': '2.2.3.4',
                }],
                'TTL': 61,
            }],
            'IsTruncated': False,
            'MaxItems': '100',
        }
        stubber.add_response('list_resource_record_sets',
                             list_resource_record_sets_resp,
                             {'HostedZoneId': 'z42'})

        stubber.add_response('list_health_checks',
                             {
                                 'HealthChecks': self.health_checks,
                                 'IsTruncated': False,
                                 'MaxItems': '100',
                                 'Marker': '',
                             })

        stubber.add_response('change_resource_record_sets',
                             {'ChangeInfo': {
                                 'Id': 'id',
                                 'Status': 'PENDING',
                                 'SubmittedAt': '2017-01-29T01:02:03Z',
                             }}, {'HostedZoneId': 'z42', 'ChangeBatch': ANY})

        self.assertEquals(9, provider.apply(plan))
        stubber.assert_no_pending_responses()

    def test_health_checks_pagination(self):
        provider, stubber = self._get_stubbed_provider()

        health_checks_p1 = [{
            'Id': '42',
            'CallerReference': self.caller_ref,
            'HealthCheckConfig': {
                'Type': 'HTTPS',
                'FullyQualifiedDomainName': 'unit.tests',
                'IPAddress': '4.2.3.4',
                'ResourcePath': '/_dns',
                'Type': 'HTTPS',
                'Port': 443,
                'MeasureLatency': True,
            },
            'HealthCheckVersion': 2,
        }, {
            'Id': '43',
            'CallerReference': 'abc123',
            'HealthCheckConfig': {
                'Type': 'HTTPS',
                'FullyQualifiedDomainName': 'unit.tests',
                'IPAddress': '9.2.3.4',
                'ResourcePath': '/_dns',
                'Type': 'HTTPS',
                'Port': 443,
                'MeasureLatency': True,
            },
            'HealthCheckVersion': 2,
        }]
        stubber.add_response('list_health_checks',
                             {
                                 'HealthChecks': health_checks_p1,
                                 'IsTruncated': True,
                                 'MaxItems': '2',
                                 'Marker': '',
                                 'NextMarker': 'moar',
                             })

        health_checks_p2 = [{
            'Id': '44',
            'CallerReference': self.caller_ref,
            'HealthCheckConfig': {
                'Type': 'HTTPS',
                'FullyQualifiedDomainName': 'unit.tests',
                'IPAddress': '8.2.3.4',
                'ResourcePath': '/_dns',
                'Type': 'HTTPS',
                'Port': 443,
                'MeasureLatency': True,
            },
            'HealthCheckVersion': 2,
        }]
        stubber.add_response('list_health_checks',
                             {
                                 'HealthChecks': health_checks_p2,
                                 'IsTruncated': False,
                                 'MaxItems': '2',
                                 'Marker': 'moar',
                             }, {'Marker': 'moar'})

        health_checks = provider.health_checks
        self.assertEquals({
            '42': health_checks_p1[0],
            '44': health_checks_p2[0],
        }, health_checks)
        stubber.assert_no_pending_responses()

        # get without create
        record = Record.new(self.expected, '', {
            'ttl': 61,
            'type': 'A',
            'values': ['2.2.3.4', '3.2.3.4'],
            'geo': {
                'AF': ['4.2.3.4'],
            }
        })
        value = record.geo['AF'].values[0]
        id = provider.get_health_check_id(record, value, True)
        self.assertEquals('42', id)

    def test_health_check_create(self):
        provider, stubber = self._get_stubbed_provider()

        # No match based on type
        caller_ref = \
            '{}:AAAA:foo1234'.format(Route53Provider.HEALTH_CHECK_VERSION)
        health_checks = [{
            'Id': '42',
            # No match based on version
            'CallerReference': '9999:A:foo1234',
            'HealthCheckConfig': {
                'Type': 'HTTPS',
                'FullyQualifiedDomainName': 'unit.tests',
                'IPAddress': '4.2.3.4',
                'ResourcePath': '/_dns',
                'Type': 'HTTPS',
                'Port': 443,
                'MeasureLatency': True,
            },
            'HealthCheckVersion': 2,
        }, {
            'Id': '43',
            'CallerReference': caller_ref,
            'HealthCheckConfig': {
                'Type': 'HTTPS',
                'FullyQualifiedDomainName': 'unit.tests',
                'IPAddress': '4.2.3.4',
                'ResourcePath': '/_dns',
                'Type': 'HTTPS',
                'Port': 443,
                'MeasureLatency': True,
            },
            'HealthCheckVersion': 2,
        }]
        stubber.add_response('list_health_checks', {
            'HealthChecks': health_checks,
            'IsTruncated': False,
            'MaxItems': '100',
            'Marker': '',
        })

        health_check_config = {
            'EnableSNI': False,
            'FailureThreshold': 6,
            'FullyQualifiedDomainName': 'foo.bar.com',
            'IPAddress': '4.2.3.4',
            'MeasureLatency': True,
            'Port': 8080,
            'RequestInterval': 10,
            'ResourcePath': '/_status',
            'Type': 'HTTP'
        }
        stubber.add_response('create_health_check', {
            'HealthCheck': {
                'Id': '42',
                'CallerReference': self.caller_ref,
                'HealthCheckConfig': health_check_config,
                'HealthCheckVersion': 1,
            },
            'Location': 'http://url',
        }, {
            'CallerReference': ANY,
            'HealthCheckConfig': health_check_config,
        })
        stubber.add_response('change_tags_for_resource', {})

        record = Record.new(self.expected, '', {
            'ttl': 61,
            'type': 'A',
            'values': ['2.2.3.4', '3.2.3.4'],
            'geo': {
                'AF': ['4.2.3.4'],
            },
            'octodns': {
                'healthcheck': {
                    'host': 'foo.bar.com',
                    'path': '/_status',
                    'port': 8080,
                    'protocol': 'HTTP',
                },
            }
        })

        # if not allowed to create returns none
        value = record.geo['AF'].values[0]
        id = provider.get_health_check_id(record, value, False)
        self.assertFalse(id)

        # when allowed to create we do
        id = provider.get_health_check_id(record, value, True)
        self.assertEquals('42', id)
        stubber.assert_no_pending_responses()

        # A CNAME style healthcheck, without a value

        health_check_config = {
            'EnableSNI': False,
            'FailureThreshold': 6,
            'FullyQualifiedDomainName': 'target-1.unit.tests.',
            'MeasureLatency': True,
            'Port': 8080,
            'RequestInterval': 10,
            'ResourcePath': '/_status',
            'Type': 'HTTP'
        }
        stubber.add_response('create_health_check', {
            'HealthCheck': {
                'Id': '42',
                'CallerReference': self.caller_ref,
                'HealthCheckConfig': health_check_config,
                'HealthCheckVersion': 1,
            },
            'Location': 'http://url',
        }, {
            'CallerReference': ANY,
            'HealthCheckConfig': health_check_config,
        })
        stubber.add_response('change_tags_for_resource', {})

        id = provider.get_health_check_id(record, 'target-1.unit.tests.', True)
        self.assertEquals('42', id)
        stubber.assert_no_pending_responses()

    def test_health_check_measure_latency(self):
        provider, stubber = self._get_stubbed_provider()
        record_true = Record.new(self.expected, 'a', {
            'ttl': 61,
            'type': 'A',
            'value': '1.2.3.4',
            'octodns': {
                'healthcheck': {
                },
                'route53': {
                    'healthcheck': {
                        'measure_latency': True
                    }
                }
            }
        })
        measure_latency = provider._healthcheck_measure_latency(record_true)
        self.assertTrue(measure_latency)

        record_default = Record.new(self.expected, 'a', {
            'ttl': 61,
            'type': 'A',
            'value': '1.2.3.4',
        })
        measure_latency = provider._healthcheck_measure_latency(record_default)
        self.assertTrue(measure_latency)

        record_false = Record.new(self.expected, 'a', {
            'ttl': 61,
            'type': 'A',
            'value': '1.2.3.4',
            'octodns': {
                'healthcheck': {
                },
                'route53': {
                    'healthcheck': {
                        'measure_latency': False
                    }
                }
            }
        })
        measure_latency = provider._healthcheck_measure_latency(record_false)
        self.assertFalse(measure_latency)

    def test_create_health_checks_measure_latency(self):
        provider, stubber = self._get_stubbed_provider()

        health_check_config = {
            'EnableSNI': True,
            'FailureThreshold': 6,
            'FullyQualifiedDomainName': 'a.unit.tests',
            'IPAddress': '1.2.3.4',
            'MeasureLatency': False,
            'Port': 443,
            'RequestInterval': 10,
            'ResourcePath': '/_dns',
            'Type': 'HTTPS'
        }

        stubber.add_response('list_health_checks', {
            'HealthChecks': [],
            'IsTruncated': False,
            'MaxItems': '100',
            'Marker': '',
        })

        stubber.add_response('create_health_check', {
            'HealthCheck': {
                'Id': '42',
                'CallerReference': self.caller_ref,
                'HealthCheckConfig': health_check_config,
                'HealthCheckVersion': 1,
            },
            'Location': 'http://url',
        }, {
            'CallerReference': ANY,
            'HealthCheckConfig': health_check_config,
        })
        stubber.add_response('change_tags_for_resource', {})
        stubber.add_response('change_tags_for_resource', {})

        record = Record.new(self.expected, 'a', {
            'ttl': 61,
            'type': 'A',
            'value': '2.2.3.4',
            'geo': {
                'AF': ['1.2.3.4'],
            },
            'octodns': {
                'healthcheck': {
                },
                'route53': {
                    'healthcheck': {
                        'measure_latency': False
                    }
                }
            }
        })

        value = record.geo['AF'].values[0]
        id = provider.get_health_check_id(record, value, True)
        ml = provider.health_checks[id]['HealthCheckConfig']['MeasureLatency']
        self.assertEqual(False, ml)

    def test_health_check_gc(self):
        provider, stubber = self._get_stubbed_provider()

        stubber.add_response('list_health_checks', {
            'HealthChecks': self.health_checks,
            'IsTruncated': False,
            'MaxItems': '100',
            'Marker': '',
        })

        record = Record.new(self.expected, '', {
            'ttl': 61,
            'type': 'A',
            'values': ['2.2.3.4', '3.2.3.4'],
            'geo': {
                'AF': ['4.2.3.4'],
                'NA-US': ['5.2.3.4', '6.2.3.4'],
                # removed one geo
            }
        })

        # gc no longer in_use records (directly)
        stubber.add_response('delete_health_check', {}, {
            'HealthCheckId': '44',
        })
        provider._gc_health_checks(record, [
            DummyR53Record('42'),
            DummyR53Record('43'),
        ])
        stubber.assert_no_pending_responses()

        # gc through _mod_Create
        stubber.add_response('delete_health_check', {}, {
            'HealthCheckId': '44',
        })
        change = Create(record)
        provider._mod_Create(change, 'z43', [])
        stubber.assert_no_pending_responses()

        # gc through _mod_Update
        stubber.add_response('delete_health_check', {}, {
            'HealthCheckId': '44',
        })
        # first record is ignored for our purposes, we have to pass something
        change = Update(record, record)
        provider._mod_Create(change, 'z43', [])
        stubber.assert_no_pending_responses()

        # gc through _mod_Delete, expect 3 to go away, can't check order
        # b/c it's not deterministic
        stubber.add_response('delete_health_check', {}, {
            'HealthCheckId': ANY,
        })
        stubber.add_response('delete_health_check', {}, {
            'HealthCheckId': ANY,
        })
        stubber.add_response('delete_health_check', {}, {
            'HealthCheckId': ANY,
        })
        change = Delete(record)
        provider._mod_Delete(change, 'z43', [])
        stubber.assert_no_pending_responses()

        # gc only AAAA, leave the A's alone
        stubber.add_response('delete_health_check', {}, {
            'HealthCheckId': '45',
        })
        record = Record.new(self.expected, '', {
            'ttl': 61,
            'type': 'AAAA',
            'value': '2001:0db8:3c4d:0015:0000:0000:1a2f:1a4b'
        })
        provider._gc_health_checks(record, [])
        stubber.assert_no_pending_responses()

    def test_legacy_health_check_gc(self):
        provider, stubber = self._get_stubbed_provider()

        old_caller_ref = '0000:A:3333'
        health_checks = [{
            'Id': '42',
            'CallerReference': self.caller_ref,
            'HealthCheckConfig': {
                'Type': 'HTTPS',
                'FullyQualifiedDomainName': 'unit.tests',
                'IPAddress': '4.2.3.4',
                'ResourcePath': '/_dns',
                'Type': 'HTTPS',
                'Port': 443,
                'MeasureLatency': True,
            },
            'HealthCheckVersion': 2,
        }, {
            'Id': '43',
            'CallerReference': old_caller_ref,
            'HealthCheckConfig': {
                'Type': 'HTTPS',
                'FullyQualifiedDomainName': 'unit.tests',
                'IPAddress': '4.2.3.4',
                'ResourcePath': '/_dns',
                'Type': 'HTTPS',
                'Port': 443,
                'MeasureLatency': True,
            },
            'HealthCheckVersion': 2,
        }, {
            'Id': '44',
            'CallerReference': old_caller_ref,
            'HealthCheckConfig': {
                'Type': 'HTTPS',
                'FullyQualifiedDomainName': 'other.unit.tests',
                'IPAddress': '4.2.3.4',
                'ResourcePath': '/_dns',
                'Type': 'HTTPS',
                'Port': 443,
                'MeasureLatency': True,
            },
            'HealthCheckVersion': 2,
        }]

        stubber.add_response('list_health_checks', {
            'HealthChecks': health_checks,
            'IsTruncated': False,
            'MaxItems': '100',
            'Marker': '',
        })

        # No changes to the record itself
        record = Record.new(self.expected, '', {
            'ttl': 61,
            'type': 'A',
            'values': ['2.2.3.4', '3.2.3.4'],
            'geo': {
                'AF': ['4.2.3.4'],
                'NA-US': ['5.2.3.4', '6.2.3.4'],
                'NA-US-CA': ['7.2.3.4']
            }
        })

        # Expect to delete the legacy hc for our record, but not touch the new
        # one or the other legacy record
        stubber.add_response('delete_health_check', {}, {
            'HealthCheckId': '43',
        })

        provider._gc_health_checks(record, [
            DummyR53Record('42'),
        ])

    def test_no_extra_changes(self):
        provider, stubber = self._get_stubbed_provider()

        list_hosted_zones_resp = {
            'HostedZones': [{
                'Name': 'unit.tests.',
                'Id': 'z42',
                'CallerReference': 'abc',
            }],
            'Marker': 'm',
            'IsTruncated': False,
            'MaxItems': '100',
        }
        stubber.add_response('list_hosted_zones', list_hosted_zones_resp, {})

        # empty is empty
        desired = Zone('unit.tests.', [])
        extra = provider._extra_changes(desired=desired, changes=[])
        self.assertEquals([], extra)
        stubber.assert_no_pending_responses()

        # single record w/o geo is empty
        desired = Zone('unit.tests.', [])
        record = Record.new(desired, 'a', {
            'ttl': 30,
            'type': 'A',
            'value': '1.2.3.4',
        })
        desired.add_record(record)
        extra = provider._extra_changes(desired=desired, changes=[])
        self.assertEquals([], extra)
        stubber.assert_no_pending_responses()

        # short-circuit for unknown zone
        other = Zone('other.tests.', [])
        extra = provider._extra_changes(desired=other, changes=[])
        self.assertEquals([], extra)
        stubber.assert_no_pending_responses()

    def test_extra_change_no_health_check(self):
        provider, stubber = self._get_stubbed_provider()

        list_hosted_zones_resp = {
            'HostedZones': [{
                'Name': 'unit.tests.',
                'Id': 'z42',
                'CallerReference': 'abc',
            }],
            'Marker': 'm',
            'IsTruncated': False,
            'MaxItems': '100',
        }
        stubber.add_response('list_hosted_zones', list_hosted_zones_resp, {})

        # record with geo and no health check returns change
        desired = Zone('unit.tests.', [])
        record = Record.new(desired, 'a', {
            'ttl': 30,
            'type': 'A',
            'value': '1.2.3.4',
            'geo': {
                'NA': ['2.2.3.4'],
            }
        })
        desired.add_record(record)
        list_resource_record_sets_resp = {
            'ResourceRecordSets': [{
                'Name': 'a.unit.tests.',
                'Type': 'A',
                'GeoLocation': {
                    'ContinentCode': 'NA',
                },
                'ResourceRecords': [{
                    'Value': '2.2.3.4',
                }],
                'TTL': 61,
            }],
            'IsTruncated': False,
            'MaxItems': '100',
        }
        stubber.add_response('list_resource_record_sets',
                             list_resource_record_sets_resp,
                             {'HostedZoneId': 'z42'})
        extra = provider._extra_changes(desired=desired, changes=[])
        self.assertEquals(1, len(extra))
        stubber.assert_no_pending_responses()

    def test_extra_change_has_wrong_health_check(self):
        provider, stubber = self._get_stubbed_provider()

        list_hosted_zones_resp = {
            'HostedZones': [{
                'Name': 'unit.tests.',
                'Id': 'z42',
                'CallerReference': 'abc',
            }],
            'Marker': 'm',
            'IsTruncated': False,
            'MaxItems': '100',
        }
        stubber.add_response('list_hosted_zones', list_hosted_zones_resp, {})

        # record with geo and no health check returns change
        desired = Zone('unit.tests.', [])
        record = Record.new(desired, 'a', {
            'ttl': 30,
            'type': 'A',
            'value': '1.2.3.4',
            'geo': {
                'NA': ['2.2.3.4'],
            }
        })
        desired.add_record(record)
        list_resource_record_sets_resp = {
            'ResourceRecordSets': [{
                'Name': 'a.unit.tests.',
                'Type': 'A',
                'GeoLocation': {
                    'ContinentCode': 'NA',
                },
                'ResourceRecords': [{
                    'Value': '2.2.3.4',
                }],
                'TTL': 61,
                'HealthCheckId': '42',
            }],
            'IsTruncated': False,
            'MaxItems': '100',
        }
        stubber.add_response('list_resource_record_sets',
                             list_resource_record_sets_resp,
                             {'HostedZoneId': 'z42'})
        stubber.add_response('list_health_checks', {
            'HealthChecks': [{
                'Id': '42',
                'CallerReference': 'foo',
                'HealthCheckConfig': {
                    'Type': 'HTTPS',
                    'FullyQualifiedDomainName': 'unit.tests',
                    'IPAddress': '2.2.3.4',
                    'ResourcePath': '/_dns',
                    'Type': 'HTTPS',
                    'Port': 443,
                    'MeasureLatency': True,
                },
                'HealthCheckVersion': 2,
            }],
            'IsTruncated': False,
            'MaxItems': '100',
            'Marker': '',
        })
        extra = provider._extra_changes(desired=desired, changes=[])
        self.assertEquals(1, len(extra))
        stubber.assert_no_pending_responses()

        for change in (Create(record), Update(record, record), Delete(record)):
            extra = provider._extra_changes(desired=desired, changes=[change])
            self.assertEquals(0, len(extra))
            stubber.assert_no_pending_responses()

    def test_extra_change_has_health_check(self):
        provider, stubber = self._get_stubbed_provider()

        list_hosted_zones_resp = {
            'HostedZones': [{
                'Name': 'unit.tests.',
                'Id': 'z42',
                'CallerReference': 'abc',
            }],
            'Marker': 'm',
            'IsTruncated': False,
            'MaxItems': '100',
        }
        stubber.add_response('list_hosted_zones', list_hosted_zones_resp, {})

        # record with geo and no health check returns change
        desired = Zone('unit.tests.', [])
        record = Record.new(desired, 'a', {
            'ttl': 30,
            'type': 'A',
            'value': '1.2.3.4',
            'geo': {
                'NA': ['2.2.3.4'],
            }
        })
        desired.add_record(record)
        list_resource_record_sets_resp = {
            'ResourceRecordSets': [{
                # other name
                'Name': 'unit.tests.',
                'Type': 'A',
                'GeoLocation': {
                    'CountryCode': '*',
                },
                'ResourceRecords': [{
                    'Value': '1.2.3.4',
                }],
                'TTL': 61,
            }, {
                # matching name, other type
                'Name': 'a.unit.tests.',
                'Type': 'AAAA',
                'ResourceRecords': [{
                    'Value': '2001:0db8:3c4d:0015:0000:0000:1a2f:1a4b'
                }],
                'TTL': 61,
            }, {
                # default geo
                'Name': 'a.unit.tests.',
                'Type': 'A',
                'GeoLocation': {
                    'CountryCode': '*',
                },
                'ResourceRecords': [{
                    'Value': '1.2.3.4',
                }],
                'TTL': 61,
            }, {
                # match w/correct geo
                'Name': 'a.unit.tests.',
                'Type': 'A',
                'GeoLocation': {
                    'ContinentCode': 'NA',
                },
                'ResourceRecords': [{
                    'Value': '2.2.3.4',
                }],
                'TTL': 61,
                'HealthCheckId': '42',
            }],
            'IsTruncated': False,
            'MaxItems': '100',
        }
        stubber.add_response('list_resource_record_sets',
                             list_resource_record_sets_resp,
                             {'HostedZoneId': 'z42'})
        stubber.add_response('list_health_checks', {
            'HealthChecks': [{
                'Id': '42',
                'CallerReference': self.caller_ref,
                'HealthCheckConfig': {
                    'Type': 'HTTPS',
                    'FullyQualifiedDomainName': 'a.unit.tests',
                    'IPAddress': '2.2.3.4',
                    'ResourcePath': '/_dns',
                    'Type': 'HTTPS',
                    'Port': 443,
                    'MeasureLatency': True
                },
                'HealthCheckVersion': 2,
            }],
            'IsTruncated': False,
            'MaxItems': '100',
            'Marker': '',
        })
        extra = provider._extra_changes(desired=desired, changes=[])
        self.assertEquals(0, len(extra))
        stubber.assert_no_pending_responses()

        # change b/c of healthcheck path
        record._octodns['healthcheck'] = {
            'path': '/_ready'
        }
        extra = provider._extra_changes(desired=desired, changes=[])
        self.assertEquals(1, len(extra))
        stubber.assert_no_pending_responses()

    def test_extra_change_dynamic_has_health_check(self):
        provider, stubber = self._get_stubbed_provider()

        list_hosted_zones_resp = {
            'HostedZones': [{
                'Name': 'unit.tests.',
                'Id': 'z42',
                'CallerReference': 'abc',
            }],
            'Marker': 'm',
            'IsTruncated': False,
            'MaxItems': '100',
        }
        stubber.add_response('list_hosted_zones', list_hosted_zones_resp, {})

        # record with geo and no health check returns change
        desired = Zone('unit.tests.', [])
        record = Record.new(desired, 'a', {
            'ttl': 30,
            'type': 'A',
            'value': '1.2.3.4',
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': '2.2.3.4',
                        }],
                    },
                },
                'rules': [{
                    'pool': 'one',
                }],
            },
        })
        desired.add_record(record)
        list_resource_record_sets_resp = {
            'ResourceRecordSets': [{
                # Not dynamic value and other name
                'Name': 'unit.tests.',
                'Type': 'A',
                'GeoLocation': {
                    'CountryCode': '*',
                },
                'ResourceRecords': [{
                    'Value': '1.2.3.4',
                }],
                'TTL': 61,
                # All the non-matches have a different Id so we'll fail if they
                # match
                'HealthCheckId': '33',
            }, {
                # Not dynamic value, matching name, other type
                'Name': 'a.unit.tests.',
                'Type': 'AAAA',
                'ResourceRecords': [{
                    'Value': '2001:0db8:3c4d:0015:0000:0000:1a2f:1a4b'
                }],
                'TTL': 61,
                'HealthCheckId': '33',
            }, {
                # default value pool
                'Name': '_octodns-default-value.a.unit.tests.',
                'Type': 'A',
                'GeoLocation': {
                    'CountryCode': '*',
                },
                'ResourceRecords': [{
                    'Value': '1.2.3.4',
                }],
                'TTL': 61,
                'HealthCheckId': '33',
            }, {
                # different record
                'Name': '_octodns-two-value.other.unit.tests.',
                'Type': 'A',
                'GeoLocation': {
                    'CountryCode': '*',
                },
                'ResourceRecords': [{
                    'Value': '1.2.3.4',
                }],
                'TTL': 61,
                'HealthCheckId': '33',
            }, {
                # same everything, but different type
                'Name': '_octodns-one-value.a.unit.tests.',
                'Type': 'AAAA',
                'ResourceRecords': [{
                    'Value': '2001:0db8:3c4d:0015:0000:0000:1a2f:1a4b'
                }],
                'TTL': 61,
                'HealthCheckId': '33',
            }, {
                # same everything, sub
                'Name': '_octodns-one-value.sub.a.unit.tests.',
                'Type': 'A',
                'ResourceRecords': [{
                    'Value': '1.2.3.4',
                }],
                'TTL': 61,
                'HealthCheckId': '33',
            }, {
                # match
                'Name': '_octodns-one-value.a.unit.tests.',
                'Type': 'A',
                'ResourceRecords': [{
                    'Value': '2.2.3.4',
                }],
                'TTL': 61,
                'HealthCheckId': '42',
            }],
            'IsTruncated': False,
            'MaxItems': '100',
        }
        stubber.add_response('list_resource_record_sets',
                             list_resource_record_sets_resp,
                             {'HostedZoneId': 'z42'})
        stubber.add_response('list_health_checks', {
            'HealthChecks': [{
                'Id': '42',
                'CallerReference': self.caller_ref,
                'HealthCheckConfig': {
                    'Type': 'HTTPS',
                    'FullyQualifiedDomainName': 'a.unit.tests',
                    'IPAddress': '2.2.3.4',
                    'ResourcePath': '/_dns',
                    'Type': 'HTTPS',
                    'Port': 443,
                    'MeasureLatency': True
                },
                'HealthCheckVersion': 2,
            }],
            'IsTruncated': False,
            'MaxItems': '100',
            'Marker': '',
        })
        extra = provider._extra_changes(desired=desired, changes=[])
        self.assertEquals(0, len(extra))
        stubber.assert_no_pending_responses()

        # change b/c of healthcheck path
        record._octodns['healthcheck'] = {
            'path': '/_ready'
        }
        extra = provider._extra_changes(desired=desired, changes=[])
        self.assertEquals(1, len(extra))
        stubber.assert_no_pending_responses()

        # change b/c of healthcheck host
        record._octodns['healthcheck'] = {
            'host': 'foo.bar.io'
        }
        extra = provider._extra_changes(desired=desired, changes=[])
        self.assertEquals(1, len(extra))
        stubber.assert_no_pending_responses()

    def _get_test_plan(self, max_changes):

        provider = Route53Provider('test', 'abc', '123', max_changes)

        # Use the stubber
        stubber = Stubber(provider._conn)
        stubber.activate()

        got = Zone('unit.tests.', [])

        list_hosted_zones_resp = {
            'HostedZones': [],
            'Marker': 'm',
            'IsTruncated': False,
            'MaxItems': '100',
        }
        stubber.add_response('list_hosted_zones', list_hosted_zones_resp,
                             {})

        create_hosted_zone_resp = {
            'HostedZone': {
                'Name': 'unit.tests.',
                'Id': 'z42',
                'CallerReference': 'abc',
            },
            'ChangeInfo': {
                'Id': 'a12',
                'Status': 'PENDING',
                'SubmittedAt': '2017-01-29T01:02:03Z',
                'Comment': 'hrm',
            },
            'DelegationSet': {
                'Id': 'b23',
                'CallerReference': 'blip',
                'NameServers': [
                    'n12.unit.tests.',
                ],
            },
            'Location': 'us-east-1',
        }
        stubber.add_response('create_hosted_zone',
                             create_hosted_zone_resp, {
                                 'Name': got.name,
                                 'CallerReference': ANY,
                             })

        stubber.add_response('list_health_checks',
                             {
                                 'HealthChecks': self.health_checks,
                                 'IsTruncated': False,
                                 'MaxItems': '100',
                                 'Marker': '',
                             })

        stubber.add_response('change_resource_record_sets',
                             {'ChangeInfo': {
                                 'Id': 'id',
                                 'Status': 'PENDING',
                                 'SubmittedAt': '2017-01-29T01:02:03Z',
                             }}, {'HostedZoneId': 'z42', 'ChangeBatch': ANY})

        plan = provider.plan(self.expected)

        return provider, plan

    # _get_test_plan() returns a plan with 11 modifications, 17 RRs

    @patch('octodns.provider.route53.Route53Provider._load_records')
    @patch('octodns.provider.route53.Route53Provider._really_apply')
    def test_apply_1(self, really_apply_mock, _):

        # 18 RRs with max of 19 should only get applied in one call
        provider, plan = self._get_test_plan(19)
        provider.apply(plan)
        really_apply_mock.assert_called_once()

    @patch('octodns.provider.route53.Route53Provider._load_records')
    @patch('octodns.provider.route53.Route53Provider._really_apply')
    def test_apply_2(self, really_apply_mock, _):

        # 18 RRs with max of 17 should only get applied in two calls
        provider, plan = self._get_test_plan(18)
        provider.apply(plan)
        self.assertEquals(2, really_apply_mock.call_count)

    @patch('octodns.provider.route53.Route53Provider._load_records')
    @patch('octodns.provider.route53.Route53Provider._really_apply')
    def test_apply_3(self, really_apply_mock, _):

        # with a max of seven modifications, four calls
        provider, plan = self._get_test_plan(7)
        provider.apply(plan)
        self.assertEquals(4, really_apply_mock.call_count)

    @patch('octodns.provider.route53.Route53Provider._load_records')
    @patch('octodns.provider.route53.Route53Provider._really_apply')
    def test_apply_4(self, really_apply_mock, _):

        # with a max of 11 modifications, two calls
        provider, plan = self._get_test_plan(11)
        provider.apply(plan)
        self.assertEquals(2, really_apply_mock.call_count)

    @patch('octodns.provider.route53.Route53Provider._load_records')
    @patch('octodns.provider.route53.Route53Provider._really_apply')
    def test_apply_bad(self, really_apply_mock, _):

        # with a max of 1 modifications, fail
        provider, plan = self._get_test_plan(1)
        with self.assertRaises(Exception) as ctx:
            provider.apply(plan)
        self.assertTrue('modifications' in ctx.exception.message)

    def test_semicolon_fixup(self):
        provider = Route53Provider('test', 'abc', '123')

        self.assertEquals({
            'type': 'TXT',
            'ttl': 30,
            'values': [
                'abcd\\; ef\\;g',
                'hij\\; klm\\;n',
            ],
        }, provider._data_for_quoted({
            'ResourceRecords': [{
                'Value': '"abcd; ef;g"',
            }, {
                'Value': '"hij\\; klm\\;n"',
            }],
            'TTL': 30,
            'Type': 'TXT',
        }))

    def test_client_max_attempts(self):
        provider = Route53Provider('test', 'abc', '123',
                                   client_max_attempts=42)
        # NOTE: this will break if boto ever changes the impl details...
        self.assertEquals(43, provider._conn.meta.events
                          ._unique_id_handlers['retry-config-route53']
                          ['handler']._checker.__dict__['_max_attempts'])

    def test_data_for_dynamic(self):
        provider = Route53Provider('test', 'abc', '123')

        data = provider._data_for_dynamic('', 'A', dynamic_rrsets)
        self.assertEquals(dynamic_record_data, data)

    @patch('octodns.provider.route53.Route53Provider._get_zone_id')
    @patch('octodns.provider.route53.Route53Provider._load_records')
    def test_dynamic_populate(self, load_records_mock, get_zone_id_mock):
        provider = Route53Provider('test', 'abc', '123')

        get_zone_id_mock.side_effect = ['z44']
        load_records_mock.side_effect = [dynamic_rrsets]

        got = Zone('unit.tests.', [])
        provider.populate(got)

        self.assertEquals(1, len(got.records))
        record = list(got.records)[0]
        self.assertEquals('', record.name)
        self.assertEquals('A', record._type)
        self.assertEquals([
            '1.1.2.1',
            '1.1.2.2',
        ], record.values)
        self.assertTrue(record.dynamic)

        self.assertEquals({
            'ap-southeast-1': {
                'fallback': 'us-east-1',
                'values': [{
                    'weight': 2, 'value': '1.4.1.1'
                }, {
                    'weight': 2, 'value': '1.4.1.2'
                }]
            },
            'eu-central-1': {
                'fallback': 'us-east-1',
                'values': [{
                    'weight': 1, 'value': '1.3.1.1'
                }, {
                    'weight': 1, 'value': '1.3.1.2'
                }],
            },
            'us-east-1': {
                'fallback': None,
                'values': [{
                    'weight': 1, 'value': '1.5.1.1'
                }, {
                    'weight': 1, 'value': '1.5.1.2'
                }],
            }
        }, {k: v.data for k, v in record.dynamic.pools.items()})

        self.assertEquals([
            {
                'geos': ['AS-CN', 'AS-JP'],
                'pool': 'ap-southeast-1',
            }, {
                'geos': ['EU', 'NA-US-FL'],
                'pool': 'eu-central-1',
            }, {
                'pool': 'us-east-1',
            }], [r.data for r in record.dynamic.rules])


class DummyProvider(object):

    def get_health_check_id(self, *args, **kwargs):
        return None


class TestRoute53Records(TestCase):
    existing = Zone('unit.tests.', [])
    record_a = Record.new(existing, '', {
        'geo': {
            'NA-US': ['2.2.2.2', '3.3.3.3'],
            'OC': ['4.4.4.4', '5.5.5.5']
        },
        'ttl': 99,
        'type': 'A',
        'values': ['9.9.9.9']
    })

    def test_value_fors(self):
        route53_record = _Route53Record(None, self.record_a, False)

        for value in (None, '', 'foo', 'bar', '1.2.3.4'):
            converted = route53_record._value_convert_value(value,
                                                            self.record_a)
            self.assertEquals(value, converted)

        record_txt = Record.new(self.existing, 'txt', {
            'ttl': 98,
            'type': 'TXT',
            'value': 'Not Important',
        })

        # We don't really have to test the details fo chunked_value as that's
        # tested elsewhere, we just need to make sure that it's plumbed up and
        # working
        self.assertEquals('"Not Important"', route53_record
                          ._value_convert_quoted(record_txt.values[0],
                                                 record_txt))

    def test_route53_record(self):
        a = _Route53Record(None, self.record_a, False)
        self.assertEquals(a, a)
        b = _Route53Record(None, Record.new(self.existing, '',
                                            {'ttl': 32, 'type': 'A',
                                             'values': ['8.8.8.8',
                                                        '1.1.1.1']}),
                           False)
        self.assertEquals(b, b)
        c = _Route53Record(None, Record.new(self.existing, 'other',
                                            {'ttl': 99, 'type': 'A',
                                             'values': ['9.9.9.9']}),
                           False)
        self.assertEquals(c, c)
        d = _Route53Record(None, Record.new(self.existing, '',
                                            {'ttl': 42, 'type': 'MX',
                                             'value': {
                                                 'preference': 10,
                                                 'exchange': 'foo.bar.'}}),
                           False)
        self.assertEquals(d, d)

        # Same fqdn & type is same record
        self.assertEquals(a, b)
        # Same name & different type is not the same
        self.assertNotEquals(a, d)
        # Different name & same type is not the same
        self.assertNotEquals(a, c)

        # Same everything, different class is not the same
        e = _Route53GeoDefault(None, self.record_a, False)
        self.assertNotEquals(a, e)

        provider = DummyProvider()
        f = _Route53GeoRecord(provider, self.record_a, 'NA-US',
                              self.record_a.geo['NA-US'], False)
        self.assertEquals(f, f)
        g = _Route53GeoRecord(provider, self.record_a, 'OC',
                              self.record_a.geo['OC'], False)
        self.assertEquals(g, g)

        # Geo and non-geo are not the same, using Geo as primary to get it's
        # __cmp__
        self.assertNotEquals(f, a)
        # Same everything, different geo's is not the same
        self.assertNotEquals(f, g)

        # Make sure it doesn't blow up
        a.__repr__()
        e.__repr__()
        f.__repr__()

    def test_dynamic_value_delete(self):
        provider = DummyProvider()
        geo = _Route53DynamicValue(provider, self.record_a, 'iad', '2.2.2.2',
                                   1, 0, False)

        rrset = {
            'HealthCheckId': 'x12346z',
            'Name': '_octodns-iad-value.unit.tests.',
            'ResourceRecords': [{
                'Value': '2.2.2.2'
            }],
            'SetIdentifier': 'iad-000',
            'TTL': 99,
            'Type': 'A',
            'Weight': 1,
        }

        candidates = [
            # Empty, will test no SetIdentifier
            {},
            # Non-matching
            {
                'SetIdentifier': 'not-a-match',
            },
            # Same set-id, different name
            {
                'Name': 'not-a-match',
                'SetIdentifier': 'x12346z',
            },
            rrset,
        ]

        # Provide a matching rrset so that we'll just use it for the delete
        # rathr than building up an almost identical one, note the way we'll
        # know that we got the one we passed in is that it'll have a
        # HealthCheckId and one that was created wouldn't since DummyProvider
        # stubs out the lookup for them
        mod = geo.mod('DELETE', candidates)
        self.assertEquals('x12346z', mod['ResourceRecordSet']['HealthCheckId'])

        # If we don't provide the candidate rrsets we get back exactly what we
        # put in minus the healthcheck
        rrset['HealthCheckId'] = None
        mod = geo.mod('DELETE', [])
        self.assertEquals(rrset, mod['ResourceRecordSet'])

    def test_geo_delete(self):
        provider = DummyProvider()
        geo = _Route53GeoRecord(provider, self.record_a, 'NA-US',
                                self.record_a.geo['NA-US'], False)

        rrset = {
            'GeoLocation': {
                'CountryCode': 'US'
            },
            'HealthCheckId': 'x12346z',
            'Name': 'unit.tests.',
            'ResourceRecords': [{
                'Value': '2.2.2.2'
            }, {
                'Value': '3.3.3.3'
            }],
            'SetIdentifier': 'NA-US',
            'TTL': 99,
            'Type': 'A'
        }

        candidates = [
            # Empty, will test no SetIdentifier
            {},
            {
                'SetIdentifier': 'not-a-match',
            },
            # Same set-id, different name
            {
                'Name': 'not-a-match',
                'SetIdentifier': 'x12346z',
            },
            rrset,
        ]

        # Provide a matching rrset so that we'll just use it for the delete
        # rathr than building up an almost identical one, note the way we'll
        # know that we got the one we passed in is that it'll have a
        # HealthCheckId and one that was created wouldn't since DummyProvider
        # stubs out the lookup for them
        mod = geo.mod('DELETE', candidates)
        self.assertEquals('x12346z', mod['ResourceRecordSet']['HealthCheckId'])

        # If we don't provide the candidate rrsets we get back exactly what we
        # put in minus the healthcheck
        del rrset['HealthCheckId']
        mod = geo.mod('DELETE', [])
        self.assertEquals(rrset, mod['ResourceRecordSet'])

    def test_new_dynamic(self):
        provider = Route53Provider('test', 'abc', '123')

        # Just so boto won't try and make any calls
        stubber = Stubber(provider._conn)
        stubber.activate()

        # We'll assume we create all healthchecks here, this functionality is
        # thoroughly tested elsewhere
        provider._health_checks = {}
        # When asked for a healthcheck return dummy info
        provider.get_health_check_id = lambda r, v, c: 'hc42'

        zone = Zone('unit.tests.', [])
        record = Record.new(zone, '', dynamic_record_data)

        # Convert a record into _Route53Records
        route53_records = _Route53Record.new(provider, record, 'z45',
                                             creating=True)
        self.assertEquals(18, len(route53_records))

        # Convert the route53_records into mods
        self.assertEquals([{
            'Action': 'CREATE',
            'ResourceRecordSet': {
                'HealthCheckId': 'hc42',
                'Name': '_octodns-ap-southeast-1-value.unit.tests.',
                'ResourceRecords': [{
                    'Value': '1.4.1.2'}],
                'SetIdentifier': 'ap-southeast-1-001',
                'TTL': 60,
                'Type': 'A',
                'Weight': 2
            }
        }, {
            'Action': 'CREATE',
            'ResourceRecordSet': {
                'HealthCheckId': 'hc42',
                'Name': '_octodns-ap-southeast-1-value.unit.tests.',
                'ResourceRecords': [{
                    'Value': '1.4.1.1'}],
                'SetIdentifier': 'ap-southeast-1-000',
                'TTL': 60,
                'Type': 'A',
                'Weight': 2
            }
        }, {
            'Action': 'CREATE',
            'ResourceRecordSet': {
                'AliasTarget': {
                    'DNSName': '_octodns-ap-southeast-1-pool.unit.tests.',
                    'EvaluateTargetHealth': True,
                    'HostedZoneId': 'z45'
                },
                'GeoLocation': {
                    'CountryCode': 'JP'},
                'Name': 'unit.tests.',
                'SetIdentifier': '0-ap-southeast-1-AS-JP',
                'Type': 'A'
            }
        }, {
            'Action': 'CREATE',
            'ResourceRecordSet': {
                'AliasTarget': {
                    'DNSName': '_octodns-eu-central-1-pool.unit.tests.',
                    'EvaluateTargetHealth': True,
                    'HostedZoneId': 'z45'},
                'GeoLocation': {
                    'CountryCode': 'US',
                    'SubdivisionCode': 'FL',
                },
                'Name': 'unit.tests.',
                'SetIdentifier': '1-eu-central-1-NA-US-FL',
                'Type': 'A'}
        }, {
            'Action': 'CREATE',
            'ResourceRecordSet': {
                'AliasTarget': {
                    'DNSName': '_octodns-us-east-1-pool.unit.tests.',
                    'EvaluateTargetHealth': True,
                    'HostedZoneId': 'z45'},
                'GeoLocation': {
                    'CountryCode': '*'},
                'Name': 'unit.tests.',
                'SetIdentifier': '2-us-east-1-None',
                'Type': 'A'}
        }, {
            'Action': 'CREATE',
            'ResourceRecordSet': {
                'AliasTarget': {
                    'DNSName': '_octodns-us-east-1-pool.unit.tests.',
                    'EvaluateTargetHealth': True,
                    'HostedZoneId': 'z45'},
                'Failover': 'SECONDARY',
                'Name': '_octodns-ap-southeast-1-pool.unit.tests.',
                'SetIdentifier': 'ap-southeast-1-Secondary-us-east-1',
                'Type': 'A'}
        }, {
            'Action': 'CREATE',
            'ResourceRecordSet': {
                'AliasTarget': {
                    'DNSName': '_octodns-ap-southeast-1-pool.unit.tests.',
                    'EvaluateTargetHealth': True,
                    'HostedZoneId': 'z45'},
                'GeoLocation': {
                    'CountryCode': 'CN'},
                'Name': 'unit.tests.',
                'SetIdentifier': '0-ap-southeast-1-AS-CN',
                'Type': 'A'}
        }, {
            'Action': 'CREATE',
            'ResourceRecordSet': {
                'AliasTarget': {
                    'DNSName': '_octodns-us-east-1-value.unit.tests.',
                    'EvaluateTargetHealth': True,
                    'HostedZoneId': 'z45'},
                'Failover': 'PRIMARY',
                'Name': '_octodns-us-east-1-pool.unit.tests.',
                'SetIdentifier': 'us-east-1-Primary',
                'Type': 'A'}
        }, {
            'Action': 'CREATE',
            'ResourceRecordSet': {
                'AliasTarget': {
                    'DNSName': '_octodns-eu-central-1-pool.unit.tests.',
                    'EvaluateTargetHealth': True,
                    'HostedZoneId': 'z45'},
                'GeoLocation': {
                    'ContinentCode': 'EU'},
                'Name': 'unit.tests.',
                'SetIdentifier': '1-eu-central-1-EU',
                'Type': 'A'}
        }, {
            'Action': 'CREATE',
            'ResourceRecordSet': {
                'AliasTarget': {
                    'DNSName': '_octodns-eu-central-1-value.unit.tests.',
                    'EvaluateTargetHealth': True,
                    'HostedZoneId': 'z45'},
                'Failover': 'PRIMARY',
                'Name': '_octodns-eu-central-1-pool.unit.tests.',
                'SetIdentifier': 'eu-central-1-Primary',
                'Type': 'A'}
        }, {
            'Action': 'CREATE',
            'ResourceRecordSet': {
                'Name': '_octodns-default-pool.unit.tests.',
                'ResourceRecords': [{
                    'Value': '1.1.2.1'},
                    {
                        'Value': '1.1.2.2'}],
                'TTL': 60,
                'Type': 'A'}
        }, {
            'Action': 'CREATE',
            'ResourceRecordSet': {
                'HealthCheckId': 'hc42',
                'Name': '_octodns-eu-central-1-value.unit.tests.',
                'ResourceRecords': [{
                    'Value': '1.3.1.2'}],
                'SetIdentifier': 'eu-central-1-001',
                'TTL': 60,
                'Type': 'A',
                'Weight': 1}
        }, {
            'Action': 'CREATE',
            'ResourceRecordSet': {
                'HealthCheckId': 'hc42',
                'Name': '_octodns-eu-central-1-value.unit.tests.',
                'ResourceRecords': [{
                    'Value': '1.3.1.1'}],
                'SetIdentifier': 'eu-central-1-000',
                'TTL': 60,
                'Type': 'A',
                'Weight': 1}
        }, {
            'Action': 'CREATE',
            'ResourceRecordSet': {
                'AliasTarget': {
                    'DNSName': '_octodns-default-pool.unit.tests.',
                    'EvaluateTargetHealth': True,
                    'HostedZoneId': 'z45'},
                'Failover': 'SECONDARY',
                'Name': '_octodns-us-east-1-pool.unit.tests.',
                'SetIdentifier': 'us-east-1-Secondary-default',
                'Type': 'A'}
        }, {
            'Action': 'CREATE',
            'ResourceRecordSet': {
                'HealthCheckId': 'hc42',
                'Name': '_octodns-us-east-1-value.unit.tests.',
                'ResourceRecords': [{
                    'Value': '1.5.1.2'}],
                'SetIdentifier': 'us-east-1-001',
                'TTL': 60,
                'Type': 'A',
                'Weight': 1}
        }, {
            'Action': 'CREATE',
            'ResourceRecordSet': {
                'HealthCheckId': 'hc42',
                'Name': '_octodns-us-east-1-value.unit.tests.',
                'ResourceRecords': [{
                    'Value': '1.5.1.1'}],
                'SetIdentifier': 'us-east-1-000',
                'TTL': 60,
                'Type': 'A',
                'Weight': 1}
        }, {
            'Action': 'CREATE',
            'ResourceRecordSet': {
                'AliasTarget': {
                    'DNSName': '_octodns-ap-southeast-1-value.unit.tests.',
                    'EvaluateTargetHealth': True,
                    'HostedZoneId': 'z45'},
                'Failover': 'PRIMARY',
                'Name': '_octodns-ap-southeast-1-pool.unit.tests.',
                'SetIdentifier': 'ap-southeast-1-Primary',
                'Type': 'A'}
        }, {
            'Action': 'CREATE',
            'ResourceRecordSet': {
                'AliasTarget': {
                    'DNSName': '_octodns-us-east-1-pool.unit.tests.',
                    'EvaluateTargetHealth': True,
                    'HostedZoneId': 'z45'},
                'Failover': 'SECONDARY',
                'Name': '_octodns-eu-central-1-pool.unit.tests.',
                'SetIdentifier': 'eu-central-1-Secondary-us-east-1',
                'Type': 'A'}
        }], [r.mod('CREATE', []) for r in route53_records])

        for route53_record in route53_records:
            # Smoke test stringification
            route53_record.__repr__()


class TestModKeyer(TestCase):

    def test_mod_keyer(self):

        # First "column" is the action priority for C/R/U

        # Deletes come first
        self.assertEquals((0, 0, 'something'), _mod_keyer({
            'Action': 'DELETE',
            'ResourceRecordSet': {
                'Name': 'something',
            }
        }))

        # Creates come next
        self.assertEquals((1, 0, 'another'), _mod_keyer({
            'Action': 'CREATE',
            'ResourceRecordSet': {
                'Name': 'another',
            }
        }))

        # Upserts are the same as creates
        self.assertEquals((1, 0, 'last'), _mod_keyer({
            'Action': 'UPSERT',
            'ResourceRecordSet': {
                'Name': 'last',
            }
        }))

        # Second "column" value records tested above

        # AliasTarget primary second (to value)
        self.assertEquals((0, -1, 'thing'), _mod_keyer({
            'Action': 'DELETE',
            'ResourceRecordSet': {
                'AliasTarget': 'some-target',
                'Failover': 'PRIMARY',
                'Name': 'thing',
            }
        }))

        self.assertEquals((1, 1, 'thing'), _mod_keyer({
            'Action': 'UPSERT',
            'ResourceRecordSet': {
                'AliasTarget': 'some-target',
                'Failover': 'PRIMARY',
                'Name': 'thing',
            }
        }))

        # AliasTarget secondary third
        self.assertEquals((0, -2, 'thing'), _mod_keyer({
            'Action': 'DELETE',
            'ResourceRecordSet': {
                'AliasTarget': 'some-target',
                'Failover': 'SECONDARY',
                'Name': 'thing',
            }
        }))

        self.assertEquals((1, 2, 'thing'), _mod_keyer({
            'Action': 'UPSERT',
            'ResourceRecordSet': {
                'AliasTarget': 'some-target',
                'Failover': 'SECONDARY',
                'Name': 'thing',
            }
        }))

        # GeoLocation fourth
        self.assertEquals((0, -3, 'some-id'), _mod_keyer({
            'Action': 'DELETE',
            'ResourceRecordSet': {
                'GeoLocation': 'some-target',
                'SetIdentifier': 'some-id',
            }
        }))

        self.assertEquals((1, 3, 'some-id'), _mod_keyer({
            'Action': 'UPSERT',
            'ResourceRecordSet': {
                'GeoLocation': 'some-target',
                'SetIdentifier': 'some-id',
            }
        }))

        # The third "column" has already been tested above, Name/SetIdentifier
