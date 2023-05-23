#
#
#

from unittest import TestCase

from octodns.record.a import ARecord, Ipv4Value
from octodns.zone import Zone


class TestRecordIp(TestCase):
    def test_ipv4_value_rdata_text(self):
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
            self.assertEqual(s, Ipv4Value.parse_rdata_text(s))

        zone = Zone('unit.tests.', [])
        a = ARecord(zone, 'a', {'ttl': 42, 'value': '1.2.3.4'})
        self.assertEqual('1.2.3.4', a.values[0].rdata_text)
