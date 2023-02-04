#
#
#

from unittest import TestCase

from octodns.record import Record
from octodns.record.exception import ValidationError
from octodns.record.spf import SpfRecord
from octodns.zone import Zone


class TestRecordSpf(TestCase):
    zone = Zone('unit.tests.', [])

    def assertMultipleValues(self, _type, a_values, b_value):
        a_data = {'ttl': 30, 'values': a_values}
        a = _type(self.zone, 'a', a_data)
        self.assertEqual('a', a.name)
        self.assertEqual('a.unit.tests.', a.fqdn)
        self.assertEqual(30, a.ttl)
        self.assertEqual(a_values, a.values)
        self.assertEqual(a_data, a.data)

        b_data = {'ttl': 30, 'value': b_value}
        b = _type(self.zone, 'b', b_data)
        self.assertEqual([b_value], b.values)
        self.assertEqual(b_data, b.data)

    def test_spf(self):
        a_values = ['spf1 -all', 'spf1 -hrm']
        b_value = 'spf1 -other'
        self.assertMultipleValues(SpfRecord, a_values, b_value)

    def test_validation(self):
        # doesn't blow up (name & zone here don't make any sense, but not
        # important)
        Record.new(
            self.zone,
            '',
            {
                'type': 'SPF',
                'ttl': 600,
                'values': [
                    'v=spf1 ip4:192.168.0.1/16-all',
                    'v=spf1 ip4:10.1.2.1/24-all',
                    'this has some\\; semi-colons\\; in it',
                ],
            },
        )

        # missing value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {'type': 'SPF', 'ttl': 600})
        self.assertEqual(['missing value(s)'], ctx.exception.reasons)

        # missing escapes
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'SPF',
                    'ttl': 600,
                    'value': 'this has some; semi-colons\\; in it',
                },
            )
        self.assertEqual(
            ['unescaped ; in "this has some; semi-colons\\; in it"'],
            ctx.exception.reasons,
        )
