#
#
#

from unittest import TestCase

from octodns.record import Record, ValidationError
from octodns.record.alias import AliasRecord
from octodns.record.target import _TargetValue
from octodns.zone import Zone


class TestRecordTarget(TestCase):
    def test_target_rdata_text(self):
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
            self.assertEqual(s, _TargetValue.parse_rdata_text(s))

        zone = Zone('unit.tests.', [])
        a = AliasRecord(zone, 'a', {'ttl': 42, 'value': 'some.target.'})
        self.assertEqual('some.target.', a.value.rdata_text)

    def test_relative_target(self):
        zone = Zone('unit.tests.', [])

        data = {'ttl': 43, 'type': 'CNAME', 'value': 'isrelative'}
        with self.assertRaises(ValidationError) as ctx:
            Record.new(zone, 'cname', data)
        self.assertEqual(
            ['CNAME value "isrelative" is relative'], ctx.exception.reasons
        )
        cname = Record.new(zone, 'cname', data, lenient=True)
        self.assertEqual(data['value'], cname.value)

        data = {
            'ttl': 43,
            'type': 'NS',
            'values': ['isrelative1', 'isrelative2'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(zone, 'ns', data)
        self.assertEqual(
            [
                'NS value "isrelative1" is relative',
                'NS value "isrelative2" is relative',
            ],
            ctx.exception.reasons,
        )
        cname = Record.new(zone, 'ns', data, lenient=True)
        self.assertEqual(data['values'], cname.values)
