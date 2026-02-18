#
#
#

from unittest import TestCase

from octodns.processor.templating import Templating
from octodns.record import Record
from octodns.record.exception import ValidationError
from octodns.record.ns import NsRecord, NsValue
from octodns.zone import Zone


class TestRecordNs(TestCase):
    zone = Zone('unit.tests.', [])

    def test_ns(self):
        a_values = ['5.6.7.8.', '6.7.8.9.', '7.8.9.0.']
        a_data = {'ttl': 30, 'values': a_values}
        a = NsRecord(self.zone, 'a', a_data)
        self.assertEqual('a', a.name)
        self.assertEqual('a.unit.tests.', a.fqdn)
        self.assertEqual(30, a.ttl)
        self.assertEqual(a_values, a.values)
        self.assertEqual(a_data, a.data)

        b_value = '9.8.7.6.'
        b_data = {'ttl': 30, 'value': b_value}
        b = NsRecord(self.zone, 'b', b_data)
        self.assertEqual([b_value], b.values)
        self.assertEqual(b_data, b.data)

    def test_ns_value_rdata_text(self):
        # anything goes, we're a noop
        for s in (
            None,
            '',
            'word',
            42,
            42.43,
            '1.2.3',
            'some.words.that.here',
            '1.2.word.4',
            '1.2.3.4',
        ):
            self.assertEqual(s, NsValue.parse_rdata_text(s))

        zone = Zone('unit.tests.', [])
        a = NsRecord(zone, 'a', {'ttl': 42, 'value': 'some.target.'})
        self.assertEqual('some.target.', a.values[0].rdata_text)

    def test_validation(self):
        # doesn't blow up
        Record.new(
            self.zone,
            '',
            {'type': 'NS', 'ttl': 600, 'values': ['foo.bar.com.', '1.2.3.4.']},
        )

        # missing value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {'type': 'NS', 'ttl': 600})
        self.assertEqual(['missing value(s)'], ctx.exception.reasons)

        # no trailing .
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone, '', {'type': 'NS', 'ttl': 600, 'value': 'foo.bar'}
            )
        self.assertEqual(
            ['NS value "foo.bar" missing trailing .'], ctx.exception.reasons
        )

        # exchange must be a valid FQDN
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {'type': 'NS', 'ttl': 600, 'value': '100 foo.bar.com.'},
            )
        self.assertEqual(
            ['NS value "100 foo.bar.com." is not a valid FQDN'],
            ctx.exception.reasons,
        )

    def test_template_validation(self):
        templ = Templating('test')

        zone = Zone('unit.tests.', [])
        ns = Record.new(
            zone,
            '',
            {'type': 'NS', 'ttl': 600, 'value': '{zone_name}example.com.'},
            lenient=False,
        )
        zone.add_record(ns)

        # Should not raise any ValidationError related to the templating
        # variables as target value validation must takes place after variables
        # substitution.
        templ.process_source_and_target_zones(zone, None, None)

        ns = Record.new(
            zone,
            '',
            {
                'type': 'NS',
                'ttl': 600,
                # Value is missing ending trailing
                'value': '{zone_name}example.com',
            },
            lenient=False,
        )
        zone.add_record(ns, replace=True)

        with self.assertRaises(ValidationError) as ctx:
            templ.process_source_and_target_zones(zone, None, None)
        self.assertEqual(
            ['NS value "unit.tests.example.com" missing trailing .'],
            ctx.exception.reasons,
        )
