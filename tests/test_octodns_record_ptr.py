#
#
#

from unittest import TestCase

from octodns.record import Record
from octodns.record.exception import ValidationError
from octodns.record.ptr import PtrRecord, PtrValue
from octodns.zone import Zone


class TestRecordPtr(TestCase):
    zone = Zone('unit.tests.', [])

    def test_ptr_lowering_value(self):
        upper_record = PtrRecord(
            self.zone,
            'PtrUppwerValue',
            {'ttl': 30, 'type': 'PTR', 'value': 'GITHUB.COM.'},
        )
        lower_record = PtrRecord(
            self.zone,
            'PtrLowerValue',
            {'ttl': 30, 'type': 'PTR', 'value': 'github.com.'},
        )
        self.assertEqual(upper_record.value, lower_record.value)

    def test_ptr(self):
        # doesn't blow up (name & zone here don't make any sense, but not
        # important)
        Record.new(
            self.zone, '', {'type': 'PTR', 'ttl': 600, 'value': 'foo.bar.com.'}
        )

        # missing value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {'type': 'PTR', 'ttl': 600})
        self.assertEqual(['missing value(s)'], ctx.exception.reasons)

        # empty value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {'type': 'PTR', 'ttl': 600, 'value': ''})
        self.assertEqual(['missing value(s)'], ctx.exception.reasons)

        # not a valid FQDN
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone, '', {'type': 'PTR', 'ttl': 600, 'value': '_.'}
            )
        self.assertEqual(
            ['Invalid PTR value "_." is not a valid FQDN.'],
            ctx.exception.reasons,
        )

        # no trailing .
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone, '', {'type': 'PTR', 'ttl': 600, 'value': 'foo.bar'}
            )
        self.assertEqual(
            ['PTR value "foo.bar" missing trailing .'], ctx.exception.reasons
        )

    def test_ptr_rdata_text(self):
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
            self.assertEqual(s, PtrValue.parse_rdata_text(s))

        zone = Zone('unit.tests.', [])
        a = PtrRecord(zone, 'a', {'ttl': 42, 'value': 'some.target.'})
        self.assertEqual('some.target.', a.values[0].rdata_text)

        a = PtrRecord(
            zone, 'a', {'ttl': 42, 'values': ['some.target.', 'second.target.']}
        )
        self.assertEqual('second.target.', a.values[0].rdata_text)
        self.assertEqual('some.target.', a.values[1].rdata_text)
