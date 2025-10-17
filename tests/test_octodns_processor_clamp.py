from unittest import TestCase

from octodns.processor.clamp import TTLArgumentException, TtlClampProcessor
from octodns.record.base import Record
from octodns.zone import Zone


class TestClampProcessor(TestCase):

    def test_processor_min(self):
        "Test the processor for clamping to the minimum"
        min_ttl = 42
        processor = TtlClampProcessor('test', min_ttl=min_ttl)

        too_low_ttl = 23
        self.assertLess(too_low_ttl, min_ttl)

        zone = Zone('unit.tests.', [])
        zone.add_record(
            Record.new(
                zone, '', {'type': 'TXT', 'ttl': too_low_ttl, 'value': 'foo'}
            )
        )

        processed_zone = processor.process_source_zone(zone.copy(), None)
        self.assertNotEqual(zone, processed_zone)

        self.assertEqual(len(processed_zone.records), len(zone.records))
        self.assertEqual(len(processed_zone.records), 1)
        self.assertEqual(processed_zone.records.pop().ttl, min_ttl)

    def test_processor_max(self):
        "Test the processor for clamping to the maximum"
        max_ttl = 4711
        processor = TtlClampProcessor('test', max_ttl=max_ttl)

        too_high_ttl = max_ttl + 1
        self.assertLess(max_ttl, too_high_ttl)

        zone = Zone('unit.tests.', [])
        zone.add_record(
            Record.new(
                zone, '', {'type': 'TXT', 'ttl': too_high_ttl, 'value': 'foo'}
            )
        )

        processed_zone = processor.process_source_zone(zone.copy(), None)
        self.assertNotEqual(zone, processed_zone)

        self.assertEqual(len(processed_zone.records), len(zone.records))
        self.assertEqual(len(processed_zone.records), 1)
        self.assertEqual(processed_zone.records.pop().ttl, max_ttl)

    def test_processor_maxmin(self):
        "Test the processor for unlogical arguments"
        min_ttl = 42
        max_ttl = 23
        self.assertRaises(
            TTLArgumentException,
            TtlClampProcessor,
            'test',
            min_ttl=min_ttl,
            max_ttl=max_ttl,
        )

    def test_processor_minmax(self):
        "Test the processor for clamping both min and max values"
        min_ttl = 42
        max_ttl = 4711
        processor = TtlClampProcessor('test', min_ttl=min_ttl, max_ttl=max_ttl)

        too_low_ttl = min_ttl - 1
        too_high_ttl = max_ttl + 1
        self.assertLess(too_low_ttl, min_ttl)
        self.assertLess(too_low_ttl, min_ttl)
        self.assertLess(max_ttl, too_high_ttl)

        zone = Zone('unit.tests.', [])
        zone.add_record(
            Record.new(
                zone,
                'high',
                {'type': 'TXT', 'ttl': too_high_ttl, 'value': 'high'},
            )
        )
        zone.add_record(
            Record.new(
                zone, 'low', {'type': 'TXT', 'ttl': too_low_ttl, 'value': 'low'}
            )
        )

        processed_zone = processor.process_source_zone(zone.copy(), None)
        self.assertNotEqual(zone, processed_zone)

        processed_records = sorted(
            list(processed_zone.records), key=lambda r: r.ttl
        )
        self.assertEqual(len(processed_records), 2)

        self.assertEqual(processed_records[0].ttl, min_ttl)
        self.assertEqual(processed_records[1].ttl, max_ttl)

    def test_processor_noclamp(self):
        "Test the processor for working with TTLs not requiring any clamping"
        min_ttl = 23
        max_ttl = 4711
        processor = TtlClampProcessor('test', min_ttl=min_ttl, max_ttl=max_ttl)

        ttl = 42

        self.assertLess(min_ttl, ttl)
        self.assertLess(ttl, max_ttl)

        zone = Zone('unit.tests.', [])
        zone.add_record(
            Record.new(zone, '', {'type': 'TXT', 'ttl': ttl, 'value': 'foo'})
        )

        processed_zone = processor.process_source_zone(zone.copy(), None)
        self.assertEqual(processed_zone.records.pop().ttl, ttl)
