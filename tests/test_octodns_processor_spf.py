from unittest import TestCase
from unittest.mock import MagicMock, call, patch

from octodns.processor.spf import (
    SpfDnsLookupException,
    SpfDnsLookupProcessor,
    SpfValueException,
)
from octodns.record.base import Record
from octodns.zone import Zone


class TestSpfDnsLookupProcessor(TestCase):
    def test_get_spf_from_txt_values(self):
        processor = SpfDnsLookupProcessor('test')

        # Used in logging
        record = Record.new(
            Zone('unit.tests.', []),
            '',
            {'type': 'TXT', 'ttl': 86400, 'values': ['']},
        )

        self.assertIsNone(
            processor._get_spf_from_txt_values(
                record, ['v=DMARC1\\; p=reject\\;']
            )
        )

        self.assertEqual(
            'v=spf1 include:example.com ~all',
            processor._get_spf_from_txt_values(
                record,
                ['v=DMARC1\\; p=reject\\;', 'v=spf1 include:example.com ~all'],
            ),
        )

        with self.assertRaises(SpfValueException):
            processor._get_spf_from_txt_values(
                record,
                [
                    'v=spf1 include:example.com ~all',
                    'v=spf1 include:example.com ~all',
                ],
            )

        # Missing "all" or "redirect" at the end
        self.assertEqual(
            'v=spf1 include:example.com',
            processor._get_spf_from_txt_values(
                record,
                ['v=spf1 include:example.com', 'v=DMARC1\\; p=reject\\;'],
            ),
        )

        self.assertEqual(
            'v=spf1 +mx redirect=example.com',
            processor._get_spf_from_txt_values(
                record,
                ['v=spf1 +mx redirect=example.com', 'v=DMARC1\\; p=reject\\;'],
            ),
        )

    @patch('dns.resolver.resolve')
    def test_processor(self, resolver_mock):
        processor = SpfDnsLookupProcessor('test')
        self.assertEqual('test', processor.name)

        zone = Zone('unit.tests.', [])
        zone.add_record(
            Record.new(
                zone,
                '',
                {
                    'type': 'TXT',
                    'ttl': 86400,
                    'values': ['v=DMARC1\\; p=reject\\;'],
                },
            )
        )
        zone.add_record(
            Record.new(
                zone, '', {'type': 'A', 'ttl': 86400, 'value': '1.2.3.4'}
            )
        )

        self.assertEqual(zone, processor.process_source_zone(zone))

        zone = Zone('unit.tests.', [])
        zone.add_record(
            Record.new(
                zone,
                '',
                {
                    'type': 'TXT',
                    'ttl': 86400,
                    'values': [
                        'v=spf1 a include:example.com ~all',
                        'v=DMARC1\\; p=reject\\;',
                    ],
                },
            )
        )

        resolver_mock.reset_mock(return_value=True, side_effect=True)
        txt_value_mock = MagicMock()
        txt_value_mock.to_text.return_value = '"v=spf1 -all"'
        resolver_mock.return_value = [txt_value_mock]

        self.assertEqual(zone, processor.process_source_zone(zone))
        resolver_mock.assert_called_once_with('example.com', 'TXT')

        zone = Zone('unit.tests.', [])
        zone.add_record(
            Record.new(
                zone,
                '',
                {
                    'type': 'TXT',
                    'ttl': 86400,
                    'values': [
                        'v=spf1 a ip4:1.2.3.4 ip6:2001:0db8:85a3:0000:0000:8a2e:0370:7334 -all',
                        'v=DMARC1\\; p=reject\\;',
                    ],
                },
            )
        )

        self.assertEqual(zone, processor.process_source_zone(zone))

        zone = Zone('unit.tests.', [])
        zone.add_record(
            Record.new(
                zone,
                '',
                {
                    'type': 'TXT',
                    'ttl': 86400,
                    'values': [
                        'v=spf1 a mx exists:example.com a a a a a a a a ~all',
                        'v=DMARC1\\; p=reject\\;',
                    ],
                },
            )
        )

        with self.assertRaises(SpfDnsLookupException):
            processor.process_source_zone(zone)

        zone = Zone('unit.tests.', [])
        zone.add_record(
            Record.new(
                zone,
                '',
                {
                    'type': 'TXT',
                    'ttl': 86400,
                    'values': [
                        'v=spf1 include:example.com -all',
                        'v=DMARC1\\; p=reject\\;',
                    ],
                },
            )
        )

        resolver_mock.reset_mock(return_value=True, side_effect=True)
        txt_value_mock = MagicMock()
        txt_value_mock.to_text.return_value = (
            '"v=spf1 a a a a a a a a a a a -all"'
        )
        resolver_mock.return_value = [txt_value_mock]

        with self.assertRaises(SpfDnsLookupException):
            processor.process_source_zone(zone)
        resolver_mock.assert_called_once_with('example.com', 'TXT')

        zone = Zone('unit.tests.', [])
        zone.add_record(
            Record.new(
                zone,
                '',
                {
                    'type': 'TXT',
                    'ttl': 86400,
                    'values': [
                        'v=spf1 include:example.com -all',
                        'v=DMARC1\\; p=reject\\;',
                    ],
                },
            )
        )

        resolver_mock.reset_mock(return_value=True, side_effect=True)
        txt_value_mock = MagicMock()
        txt_value_mock.to_text.return_value = (
            '"v=spf1 ip4:1.2.3.4" " ip4:4.3.2.1 -all"'
        )
        resolver_mock.return_value = [txt_value_mock]

        self.assertEqual(zone, processor.process_source_zone(zone))
        resolver_mock.assert_called_once_with('example.com', 'TXT')

        zone = Zone('unit.tests.', [])
        zone.add_record(
            Record.new(
                zone,
                '',
                {
                    'type': 'TXT',
                    'ttl': 86400,
                    'values': [
                        'v=spf1 include:example.com -all',
                        'v=DMARC1\\; p=reject\\;',
                    ],
                },
            )
        )

        resolver_mock.reset_mock(return_value=True, side_effect=True)
        first_txt_value_mock = MagicMock()
        first_txt_value_mock.to_text.return_value = (
            '"v=spf1 include:_spf.example.com -all"'
        )
        second_txt_value_mock = MagicMock()
        second_txt_value_mock.to_text.return_value = '"v=spf1 a -all"'
        resolver_mock.side_effect = [
            [first_txt_value_mock],
            [second_txt_value_mock],
        ]

        self.assertEqual(zone, processor.process_source_zone(zone))
        resolver_mock.assert_has_calls(
            [call('example.com', 'TXT'), call('_spf.example.com', 'TXT')]
        )

    def test_processor_with_long_txt_value(self):
        processor = SpfDnsLookupProcessor('test')
        zone = Zone('unit.tests.', [])

        zone.add_record(
            Record.new(
                zone,
                '',
                {
                    'type': 'TXT',
                    'ttl': 86400,
                    'value': (
                        'v=spf1 ip6:2001:0db8:85a3:0000:0000:8a2e:0370:7334 ip6:2001:0db8:85a3:0000:0000:8a2e:0370:7334'
                        ' ip6:2001:0db8:85a3:0000:0000:8a2e:0370:7334 ip6:2001:0db8:85a3:0000:0000:8a2e:0370:7334'
                        ' ip6:2001:0db8:85a3:0000:0000:8a2e:0370:7334 ip6:2001:0db8:85a3:0000:0000:8a2e:0370:7334'
                        ' ip6:2001:0db8:85a3:0000:0000:8a2e:0370:7334 ip6:2001:0db8:85a3:0000:0000:8a2e:0370:7334'
                        ' ip6:2001:0db8:85a3:0000:0000:8a2e:0370:7334 ip6:2001:0db8:85a3:0000:0000:8a2e:0370:7334'
                        ' ip6:2001:0db8:85a3:0000:0000:8a2e:0370:7334 ip6:2001:0db8:85a3:0000:0000:8a2e:0370:7334'
                        ' ip6:2001:0db8:85a3:0000:0000:8a2e:0370:7334 ~all'
                    ),
                },
            )
        )

        self.assertEqual(zone, processor.process_source_zone(zone))

    @patch('dns.resolver.resolve')
    def test_processor_with_lenient_record(self, resolver_mock):
        processor = SpfDnsLookupProcessor('test')
        zone = Zone('unit.tests.', [])

        lenient = Record.new(
            zone,
            'lenient',
            {
                'type': 'TXT',
                'ttl': 86400,
                'value': 'v=spf1 a a a a a a a a a a a ~all',
                'octodns': {'lenient': True},
            },
        )
        zone.add_record(lenient)

        self.assertEqual(zone, processor.process_source_zone(zone))
        resolver_mock.assert_not_called()

    @patch('dns.resolver.resolve')
    def test_processor_errors_on_too_many_spf_values(self, resolver_mock):
        processor = SpfDnsLookupProcessor('test')
        zone = Zone('unit.tests.', [])

        record = Record.new(
            zone,
            '',
            {
                'type': 'TXT',
                'ttl': 86400,
                'values': [
                    'v=spf1 include:_spf.google.com ~all',
                    'v=spf1 include:mailgun.org ~all',
                ],
            },
        )
        zone.add_record(record)

        with self.assertRaises(SpfValueException):
            processor.process_source_zone(zone)
        resolver_mock.assert_not_called()

    @patch('dns.resolver.resolve')
    def test_processor_errors_ptr_mechanisms(self, resolver_mock):
        processor = SpfDnsLookupProcessor('test')
        zone = Zone('unit.tests.', [])

        zone.add_record(
            Record.new(
                zone,
                '',
                {'type': 'TXT', 'ttl': 86400, 'values': ['v=spf1 ptr ~all']},
            )
        )

        with self.assertRaises(SpfValueException) as context:
            processor.process_source_zone(zone)
        self.assertEqual(
            'unit.tests. uses the deprecated ptr mechanism',
            str(context.exception),
        )
        resolver_mock.assert_not_called()

        zone = Zone('unit.tests.', [])

        zone.add_record(
            Record.new(
                zone,
                '',
                {
                    'type': 'TXT',
                    'ttl': 86400,
                    'values': ['v=spf1 ptr:example.com ~all'],
                },
            )
        )

        resolver_mock.reset_mock(return_value=True, side_effect=True)

        with self.assertRaises(SpfValueException) as context:
            processor.process_source_zone(zone)
        self.assertEqual(
            'unit.tests. uses the deprecated ptr mechanism',
            str(context.exception),
        )
        resolver_mock.assert_not_called()

        zone = Zone('unit.tests.', [])

        zone.add_record(
            Record.new(
                zone,
                '',
                {
                    'type': 'TXT',
                    'ttl': 86400,
                    'values': ['v=spf1 include:example.com ~all'],
                },
            )
        )

        resolver_mock.reset_mock(return_value=True, side_effect=True)
        txt_value_mock = MagicMock()
        txt_value_mock.to_text.return_value = '"v=spf1 ptr -all"'
        resolver_mock.return_value = [txt_value_mock]

        with self.assertRaises(SpfValueException) as context:
            processor.process_source_zone(zone)
        self.assertEqual(
            'unit.tests. uses the deprecated ptr mechanism',
            str(context.exception),
        )
        resolver_mock.assert_called_once_with('example.com', 'TXT')

    @patch('dns.resolver.resolve')
    def test_processor_errors_on_recursive_include_mechanism(
        self, resolver_mock
    ):
        processor = SpfDnsLookupProcessor('test')
        zone = Zone('unit.tests.', [])

        zone.add_record(
            Record.new(
                zone,
                '',
                {
                    'type': 'TXT',
                    'ttl': 86400,
                    'values': ['v=spf1 include:example.com ~all'],
                },
            )
        )

        txt_value_mock = MagicMock()
        txt_value_mock.to_text.return_value = (
            '"v=spf1 include:example.com ~all"'
        )
        resolver_mock.return_value = [txt_value_mock]

        with self.assertRaises(SpfDnsLookupException):
            processor.process_source_zone(zone)
        resolver_mock.assert_called_with('example.com', 'TXT')
