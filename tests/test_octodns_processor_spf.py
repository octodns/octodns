from unittest import TestCase

from octodns.processor.spf import (
    SpfDnsLookupException,
    SpfDnsLookupProcessor,
    SpfValueException,
)
from octodns.record.base import Record
from octodns.zone import Zone


class TestSpfDnsLookupProcessor(TestCase):
    def test_processor(self):
        processor = SpfDnsLookupProcessor('test')
        assert processor.name == 'test'

        processor = SpfDnsLookupProcessor('test')
        zone = Zone('unit.tests.', [])
        zone.add_record(
            Record.new(
                zone,
                '',
                {
                    'type': 'TXT',
                    'ttl': 86400,
                    'values': ['v=spf1 a ~all', 'v=DMARC1\; p=reject\;'],
                },
            )
        )

        assert zone == processor.process_source_zone(zone)
        zone = Zone('unit.tests.', [])
        zone.add_record(
            Record.new(
                zone,
                '',
                {
                    'type': 'TXT',
                    'ttl': 86400,
                    'values': [
                        'v=spf1 a a a a a a a a a a -all',
                        'v=DMARC1\; p=reject\;',
                    ],
                },
            )
        )

        assert zone == processor.process_source_zone(zone)

        zone = Zone('unit.tests.', [])
        zone.add_record(
            Record.new(
                zone,
                '',
                {
                    'type': 'TXT',
                    'ttl': 86400,
                    'values': [
                        'v=spf1 a mx exists redirect a a a a a a a ~all',
                        'v=DMARC1\; p=reject\;',
                    ],
                },
            )
        )

        with self.assertRaises(SpfDnsLookupException):
            processor.process_source_zone(zone)

    def test_processor_skips_lenient_records(self):
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

        processed = processor.process_source_zone(zone)

        assert zone == processed

    def test_processor_errors_on_many_spf_values_in_record(self):
        processor = SpfDnsLookupProcessor('test')
        zone = Zone('unit.tests.', [])

        record = Record.new(
            zone,
            '',
            {
                'type': 'TXT',
                'ttl': 86400,
                'values': [
                    'v=spf1 include:mailgun.org ~all',
                    'v=spf1 include:_spf.google.com ~all',
                ],
            },
        )
        zone.add_record(record)

        with self.assertRaises(SpfValueException):
            processor.process_source_zone(zone)

    def test_processor_filters_to_records_with_spf_values(self):
        processor = SpfDnsLookupProcessor('test')
        zone = Zone('unit.tests.', [])

        zone.add_record(
            Record.new(
                zone, '', {'type': 'A', 'ttl': 86400, 'value': '1.2.3.4'}
            )
        )
        zone.add_record(
            Record.new(
                zone,
                '',
                {
                    'type': 'TXT',
                    'ttl': 86400,
                    'value': 'v=spf1 a a a a a a a a a a a ~all',
                },
            )
        )

        with self.assertRaises(SpfDnsLookupException):
            processor.process_source_zone(zone)

        zone = Zone('unit.tests.', [])

        zone.add_record(
            Record.new(
                zone, '', {'type': 'A', 'ttl': 86400, 'value': '1.2.3.4'}
            )
        )
        zone.add_record(
            Record.new(
                zone,
                '',
                {
                    'type': 'TXT',
                    'ttl': 86400,
                    'values': ['AAAAAAAAAAA', 'v=spf10'],
                },
            )
        )

        assert zone == processor.process_source_zone(zone)
