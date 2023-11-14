#
#
#

from unittest import TestCase

from helpers import SimpleProvider

from octodns.record.base import Record
from octodns.record.exception import ValidationError
from octodns.record.rr import RrParseError
from octodns.record.sshfp import SshfpRecord, SshfpValue
from octodns.zone import Zone


class TestRecordSshfp(TestCase):
    zone = Zone('unit.tests.', [])

    def test_sshfp(self):
        a_values = [
            SshfpValue(
                {
                    'algorithm': 10,
                    'fingerprint_type': 11,
                    'fingerprint': 'abc123',
                }
            ),
            SshfpValue(
                {
                    'algorithm': 20,
                    'fingerprint_type': 21,
                    'fingerprint': 'def456',
                }
            ),
        ]
        a_data = {'ttl': 30, 'values': a_values}
        a = SshfpRecord(self.zone, 'a', a_data)
        self.assertEqual('a', a.name)
        self.assertEqual('a.unit.tests.', a.fqdn)
        self.assertEqual(30, a.ttl)
        self.assertEqual(a_values[0]['algorithm'], a.values[0].algorithm)
        self.assertEqual(
            a_values[0]['fingerprint_type'], a.values[0].fingerprint_type
        )
        self.assertEqual(a_values[0]['fingerprint'], a.values[0].fingerprint)
        self.assertEqual(a_data, a.data)

        b_value = SshfpValue(
            {'algorithm': 30, 'fingerprint_type': 31, 'fingerprint': 'ghi789'}
        )
        b_data = {'ttl': 30, 'value': b_value}
        b = SshfpRecord(self.zone, 'b', b_data)
        self.assertEqual(b_value['algorithm'], b.values[0].algorithm)
        self.assertEqual(
            b_value['fingerprint_type'], b.values[0].fingerprint_type
        )
        self.assertEqual(b_value['fingerprint'], b.values[0].fingerprint)
        self.assertEqual(b_data, b.data)

        target = SimpleProvider()
        # No changes with self
        self.assertFalse(a.changes(a, target))
        # Diff in algorithm causes change
        other = SshfpRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].algorithm = 22
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in fingerprint_type causes change
        other = SshfpRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].algorithm = a.values[0].algorithm
        other.values[0].fingerprint_type = 22
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in fingerprint causes change
        other = SshfpRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].fingerprint_type = a.values[0].fingerprint_type
        other.values[0].fingerprint = 22
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)

        # __repr__ doesn't blow up
        a.__repr__()

    def test_sshfp_value_rdata_text(self):
        # empty string won't parse
        with self.assertRaises(RrParseError):
            SshfpValue.parse_rdata_text('')

        # single word won't parse
        with self.assertRaises(RrParseError):
            SshfpValue.parse_rdata_text('nope')

        # 3rd word won't parse
        with self.assertRaises(RrParseError):
            SshfpValue.parse_rdata_text('0 1 00479b27 another')

        # algorithm and fingerprint_type not ints
        self.assertEqual(
            {
                'algorithm': 'one',
                'fingerprint_type': 'two',
                'fingerprint': '00479b27',
            },
            SshfpValue.parse_rdata_text('one two 00479b27'),
        )

        # valid
        self.assertEqual(
            {'algorithm': 1, 'fingerprint_type': 2, 'fingerprint': '00479b27'},
            SshfpValue.parse_rdata_text('1 2 00479b27'),
        )

        # valid
        self.assertEqual(
            {'algorithm': 1, 'fingerprint_type': 2, 'fingerprint': '00479b27'},
            SshfpValue.parse_rdata_text('1 2 "00479b27"'),
        )

        zone = Zone('unit.tests.', [])
        a = SshfpRecord(
            zone,
            'sshfp',
            {
                'ttl': 32,
                'value': {
                    'algorithm': 1,
                    'fingerprint_type': 2,
                    'fingerprint': '00479b27',
                },
            },
        )
        self.assertEqual(1, a.values[0].algorithm)
        self.assertEqual(2, a.values[0].fingerprint_type)
        self.assertEqual('00479b27', a.values[0].fingerprint)
        self.assertEqual('1 2 00479b27', a.values[0].rdata_text)

    def test_sshfp_value(self):
        a = SshfpValue(
            {'algorithm': 0, 'fingerprint_type': 0, 'fingerprint': 'abcd'}
        )
        b = SshfpValue(
            {'algorithm': 1, 'fingerprint_type': 0, 'fingerprint': 'abcd'}
        )
        c = SshfpValue(
            {'algorithm': 0, 'fingerprint_type': 1, 'fingerprint': 'abcd'}
        )
        d = SshfpValue(
            {'algorithm': 0, 'fingerprint_type': 0, 'fingerprint': 'bcde'}
        )

        self.assertEqual(a, a)
        self.assertEqual(b, b)
        self.assertEqual(c, c)
        self.assertEqual(d, d)

        self.assertNotEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertNotEqual(a, d)
        self.assertNotEqual(b, a)
        self.assertNotEqual(b, c)
        self.assertNotEqual(b, d)
        self.assertNotEqual(c, a)
        self.assertNotEqual(c, b)
        self.assertNotEqual(c, d)
        self.assertNotEqual(d, a)
        self.assertNotEqual(d, b)
        self.assertNotEqual(d, c)

        self.assertTrue(a < b)
        self.assertTrue(a < c)

        self.assertTrue(b > a)
        self.assertTrue(b > c)

        self.assertTrue(c > a)
        self.assertTrue(c < b)

        self.assertTrue(a <= b)
        self.assertTrue(a <= c)
        self.assertTrue(a <= a)
        self.assertTrue(a >= a)

        self.assertTrue(b >= a)
        self.assertTrue(b >= c)
        self.assertTrue(b >= b)
        self.assertTrue(b <= b)

        self.assertTrue(c >= a)
        self.assertTrue(c <= b)
        self.assertTrue(c >= c)
        self.assertTrue(c <= c)

        # Hash
        values = set()
        values.add(a)
        self.assertTrue(a in values)
        self.assertFalse(b in values)
        values.add(b)
        self.assertTrue(b in values)

    def test_validation(self):
        # doesn't blow up
        Record.new(
            self.zone,
            '',
            {
                'type': 'SSHFP',
                'ttl': 600,
                'value': {
                    'algorithm': 1,
                    'fingerprint_type': 1,
                    'fingerprint': 'bf6b6825d2977c511a475bbefb88aad54a92ac73',
                },
            },
        )

        # missing algorithm
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'SSHFP',
                    'ttl': 600,
                    'value': {
                        'fingerprint_type': 1,
                        'fingerprint': 'bf6b6825d2977c511a475bbefb88aad54a92ac73',
                    },
                },
            )
        self.assertEqual(['missing algorithm'], ctx.exception.reasons)

        # invalid algorithm
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'SSHFP',
                    'ttl': 600,
                    'value': {
                        'algorithm': 'nope',
                        'fingerprint_type': 2,
                        'fingerprint': 'bf6b6825d2977c511a475bbefb88aad54a92ac73',
                    },
                },
            )
        self.assertEqual(['invalid algorithm "nope"'], ctx.exception.reasons)

        # unrecognized algorithm
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'SSHFP',
                    'ttl': 600,
                    'value': {
                        'algorithm': 42,
                        'fingerprint_type': 1,
                        'fingerprint': 'bf6b6825d2977c511a475bbefb88aad54a92ac73',
                    },
                },
            )
        self.assertEqual(['unrecognized algorithm "42"'], ctx.exception.reasons)

        # missing fingerprint_type
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'SSHFP',
                    'ttl': 600,
                    'value': {
                        'algorithm': 2,
                        'fingerprint': 'bf6b6825d2977c511a475bbefb88aad54a92ac73',
                    },
                },
            )
        self.assertEqual(['missing fingerprint_type'], ctx.exception.reasons)

        # invalid fingerprint_type
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'SSHFP',
                    'ttl': 600,
                    'value': {
                        'algorithm': 3,
                        'fingerprint_type': 'yeeah',
                        'fingerprint': 'bf6b6825d2977c511a475bbefb88aad54a92ac73',
                    },
                },
            )
        self.assertEqual(
            ['invalid fingerprint_type "yeeah"'], ctx.exception.reasons
        )

        # unrecognized fingerprint_type
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'SSHFP',
                    'ttl': 600,
                    'value': {
                        'algorithm': 1,
                        'fingerprint_type': 42,
                        'fingerprint': 'bf6b6825d2977c511a475bbefb88aad54a92ac73',
                    },
                },
            )
        self.assertEqual(
            ['unrecognized fingerprint_type "42"'], ctx.exception.reasons
        )

        # missing fingerprint
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                '',
                {
                    'type': 'SSHFP',
                    'ttl': 600,
                    'value': {'algorithm': 1, 'fingerprint_type': 1},
                },
            )
        self.assertEqual(['missing fingerprint'], ctx.exception.reasons)
