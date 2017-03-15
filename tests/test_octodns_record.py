#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from unittest import TestCase

from octodns.record import ARecord, AaaaRecord, CnameRecord, Create, Delete, \
    GeoValue, MxRecord, NaptrRecord, NaptrValue, NsRecord, PtrRecord, Record, \
    SshfpRecord, SpfRecord, SrvRecord, TxtRecord, Update
from octodns.zone import Zone

from helpers import GeoProvider, SimpleProvider


class TestRecord(TestCase):
    zone = Zone('unit.tests.', [])

    def test_lowering(self):
        record = ARecord(self.zone, 'MiXeDcAsE', {
            'ttl': 30,
            'type': 'A',
            'value': '1.2.3.4',
        })
        self.assertEquals('mixedcase', record.name)

    def test_a_and_record(self):
        a_values = ['1.2.3.4', '2.2.3.4']
        a_data = {'ttl': 30, 'values': a_values}
        a = ARecord(self.zone, 'a', a_data)
        self.assertEquals('a', a.name)
        self.assertEquals('a.unit.tests.', a.fqdn)
        self.assertEquals(30, a.ttl)
        self.assertEquals(a_values, a.values)
        self.assertEquals(a_data, a.data)

        b_value = '3.2.3.4'
        b_data = {'ttl': 30, 'value': b_value}
        b = ARecord(self.zone, 'b', b_data)
        self.assertEquals([b_value], b.values)
        self.assertEquals(b_data, b.data)

        # missing ttl
        with self.assertRaises(Exception) as ctx:
            ARecord(self.zone, None, {'value': '1.1.1.1'})
        self.assertTrue('missing ttl' in ctx.exception.message)
        # missing values & value
        with self.assertRaises(Exception) as ctx:
            ARecord(self.zone, None, {'ttl': 42})
        self.assertTrue('missing value(s)' in ctx.exception.message)

        # top-level
        data = {'ttl': 30, 'value': '4.2.3.4'}
        self.assertEquals(self.zone.name, ARecord(self.zone, '', data).fqdn)
        self.assertEquals(self.zone.name, ARecord(self.zone, None, data).fqdn)

        # ARecord equate with itself
        self.assertTrue(a == a)
        # Records with differing names and same type don't equate
        self.assertFalse(a == b)
        # Records with same name & type equate even if ttl is different
        self.assertTrue(a == ARecord(self.zone, 'a',
                                     {'ttl': 31, 'values': a_values}))
        # Records with same name & type equate even if values are different
        self.assertTrue(a == ARecord(self.zone, 'a',
                                     {'ttl': 30, 'value': b_value}))

        target = SimpleProvider()
        # no changes if self
        self.assertFalse(a.changes(a, target))
        # no changes if clone
        other = ARecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        self.assertFalse(a.changes(other, target))
        # changes if ttl modified
        other.ttl = 31
        update = a.changes(other, target)
        self.assertEquals(a, update.existing)
        self.assertEquals(other, update.new)
        # changes if values modified
        other.ttl = a.ttl
        other.values = ['4.4.4.4']
        update = a.changes(other, target)
        self.assertEquals(a, update.existing)
        self.assertEquals(other, update.new)

        # Hashing
        records = set()
        records.add(a)
        self.assertTrue(a in records)
        self.assertFalse(b in records)
        records.add(b)
        self.assertTrue(b in records)

        # __repr__ doesn't blow up
        a.__repr__()
        # Record.__repr__ does
        with self.assertRaises(NotImplementedError):
            class DummyRecord(Record):

                def __init__(self):
                    pass

            DummyRecord().__repr__()

    def test_invalid_a(self):
        with self.assertRaises(Exception) as ctx:
            ARecord(self.zone, 'a', {
                'ttl': 30,
                'value': 'foo',
            })
        self.assertTrue('Invalid record' in ctx.exception.message)
        with self.assertRaises(Exception) as ctx:
            ARecord(self.zone, 'a', {
                'ttl': 30,
                'values': ['1.2.3.4', 'bar'],
            })
        self.assertTrue('Invalid record' in ctx.exception.message)

    def test_geo(self):
        geo_data = {'ttl': 42, 'values': ['5.2.3.4', '6.2.3.4'],
                    'geo': {'AF': ['1.1.1.1'],
                            'AS-JP': ['2.2.2.2', '3.3.3.3'],
                            'NA-US': ['4.4.4.4', '5.5.5.5'],
                            'NA-US-CA': ['6.6.6.6', '7.7.7.7']}}
        geo = ARecord(self.zone, 'geo', geo_data)
        self.assertEquals(geo_data, geo.data)

        other_data = {'ttl': 42, 'values': ['5.2.3.4', '6.2.3.4'],
                      'geo': {'AF': ['1.1.1.1'],
                              'AS-JP': ['2.2.2.2', '3.3.3.3'],
                              'NA-US': ['4.4.4.4', '5.5.5.5'],
                              'NA-US-CA': ['6.6.6.6', '7.7.7.7']}}
        other = ARecord(self.zone, 'geo', other_data)
        self.assertEquals(other_data, other.data)

        simple_target = SimpleProvider()
        geo_target = GeoProvider()

        # Geo provider doesn't consider identical geo to be changes
        self.assertFalse(geo.changes(geo, geo_target))

        # geo values don't impact equality
        other.geo['AF'].values = ['9.9.9.9']
        self.assertTrue(geo == other)
        # Non-geo supporting provider doesn't consider geo diffs to be changes
        self.assertFalse(geo.changes(other, simple_target))
        # Geo provider does consider geo diffs to be changes
        self.assertTrue(geo.changes(other, geo_target))

        # Object without geo doesn't impact equality
        other.geo = {}
        self.assertTrue(geo == other)
        # Non-geo supporting provider doesn't consider lack of geo a diff
        self.assertFalse(geo.changes(other, simple_target))
        # Geo provider does consider lack of geo diffs to be changes
        self.assertTrue(geo.changes(other, geo_target))

        # invalid geo code
        with self.assertRaises(Exception) as ctx:
            ARecord(self.zone, 'geo', {'ttl': 42,
                                       'values': ['5.2.3.4', '6.2.3.4'],
                                       'geo': {'abc': ['1.1.1.1']}})
        self.assertEquals('Invalid geo "abc"', ctx.exception.message)

        with self.assertRaises(Exception) as ctx:
            ARecord(self.zone, 'geo', {'ttl': 42,
                                       'values': ['5.2.3.4', '6.2.3.4'],
                                       'geo': {'NA-US': ['1.1.1']}})
        self.assertTrue('not a valid ip' in ctx.exception.message)

        # __repr__ doesn't blow up
        geo.__repr__()

    def assertMultipleValues(self, _type, a_values, b_value):
        a_data = {'ttl': 30, 'values': a_values}
        a = _type(self.zone, 'a', a_data)
        self.assertEquals('a', a.name)
        self.assertEquals('a.unit.tests.', a.fqdn)
        self.assertEquals(30, a.ttl)
        self.assertEquals(a_values, a.values)
        self.assertEquals(a_data, a.data)

        b_data = {'ttl': 30, 'value': b_value}
        b = _type(self.zone, 'b', b_data)
        self.assertEquals([b_value], b.values)
        self.assertEquals(b_data, b.data)

        # missing values & value
        with self.assertRaises(Exception) as ctx:
            _type(self.zone, None, {'ttl': 42})
        self.assertTrue('missing value(s)' in ctx.exception.message)

    def test_aaaa(self):
        a_values = ['2001:0db8:3c4d:0015:0000:0000:1a2f:1a2b',
                    '2001:0db8:3c4d:0015:0000:0000:1a2f:1a3b']
        b_value = '2001:0db8:3c4d:0015:0000:0000:1a2f:1a4b'
        self.assertMultipleValues(AaaaRecord, a_values, b_value)

        with self.assertRaises(Exception) as ctx:
            AaaaRecord(self.zone, 'a', {
                'ttl': 30,
                'value': 'foo',
            })
        self.assertTrue('Invalid record' in ctx.exception.message)
        with self.assertRaises(Exception) as ctx:
            AaaaRecord(self.zone, 'a', {
                'ttl': 30,
                'values': [b_value, 'bar'],
            })
        self.assertTrue('Invalid record' in ctx.exception.message)

    def assertSingleValue(self, _type, a_value, b_value):
        a_data = {'ttl': 30, 'value': a_value}
        a = _type(self.zone, 'a', a_data)
        self.assertEquals('a', a.name)
        self.assertEquals('a.unit.tests.', a.fqdn)
        self.assertEquals(30, a.ttl)
        self.assertEquals(a_value, a.value)
        self.assertEquals(a_data, a.data)

        b_data = {'ttl': 30, 'value': b_value}
        b = _type(self.zone, 'b', b_data)
        self.assertEquals(b_value, b.value)
        self.assertEquals(b_data, b.data)

        # missing value
        with self.assertRaises(Exception) as ctx:
            _type(self.zone, None, {'ttl': 42})
        self.assertTrue('missing value' in ctx.exception.message)

        target = SimpleProvider()
        # No changes with self
        self.assertFalse(a.changes(a, target))
        # Diff in value causes change
        other = _type(self.zone, 'a', {'ttl': 30, 'value': b_value})
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)

        # __repr__ doesn't blow up
        a.__repr__()

    def test_cname(self):
        self.assertSingleValue(CnameRecord, 'target.foo.com.',
                               'other.foo.com.')

        with self.assertRaises(Exception) as ctx:
            CnameRecord(self.zone, 'a', {
                'ttl': 30,
                'value': 'foo',
            })
        self.assertTrue('Invalid record' in ctx.exception.message)
        with self.assertRaises(Exception) as ctx:
            CnameRecord(self.zone, 'a', {
                'ttl': 30,
                'values': ['foo.com.', 'bar.com'],
            })
        self.assertTrue('Invalid record' in ctx.exception.message)

    def test_mx(self):
        a_values = [{
            'priority': 10,
            'value': 'smtp1'
        }, {
            'priority': 20,
            'value': 'smtp2'
        }]
        a_data = {'ttl': 30, 'values': a_values}
        a = MxRecord(self.zone, 'a', a_data)
        self.assertEquals('a', a.name)
        self.assertEquals('a.unit.tests.', a.fqdn)
        self.assertEquals(30, a.ttl)
        self.assertEquals(a_values[0]['priority'], a.values[0].priority)
        self.assertEquals(a_values[0]['value'], a.values[0].value)
        self.assertEquals(a_values[1]['priority'], a.values[1].priority)
        self.assertEquals(a_values[1]['value'], a.values[1].value)
        self.assertEquals(a_data, a.data)

        b_value = {
            'priority': 12,
            'value': 'smtp3',
        }
        b_data = {'ttl': 30, 'value': b_value}
        b = MxRecord(self.zone, 'b', b_data)
        self.assertEquals(b_value['priority'], b.values[0].priority)
        self.assertEquals(b_value['value'], b.values[0].value)
        self.assertEquals(b_data, b.data)

        # missing value
        with self.assertRaises(Exception) as ctx:
            MxRecord(self.zone, None, {'ttl': 42})
        self.assertTrue('missing value(s)' in ctx.exception.message)
        # invalid value
        with self.assertRaises(Exception) as ctx:
            MxRecord(self.zone, None, {'ttl': 42, 'value': {}})
        self.assertTrue('Invalid value' in ctx.exception.message)

        target = SimpleProvider()
        # No changes with self
        self.assertFalse(a.changes(a, target))
        # Diff in priority causes change
        other = MxRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].priority = 22
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in value causes change
        other.values[0].priority = a.values[0].priority
        other.values[0].value = 'smtpX'
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)

        # __repr__ doesn't blow up
        a.__repr__()

    def test_naptr(self):
        a_values = [{
            'order': 10,
            'preference': 11,
            'flags': 'X',
            'service': 'Y',
            'regexp': 'Z',
            'replacement': '.',
        }, {
            'order': 20,
            'preference': 21,
            'flags': 'A',
            'service': 'B',
            'regexp': 'C',
            'replacement': 'foo.com',
        }]
        a_data = {'ttl': 30, 'values': a_values}
        a = NaptrRecord(self.zone, 'a', a_data)
        self.assertEquals('a', a.name)
        self.assertEquals('a.unit.tests.', a.fqdn)
        self.assertEquals(30, a.ttl)
        for i in (0, 1):
            for k in a_values[0].keys():
                self.assertEquals(a_values[i][k], getattr(a.values[i], k))
        self.assertEquals(a_data, a.data)

        b_value = {
            'order': 30,
            'preference': 31,
            'flags': 'M',
            'service': 'N',
            'regexp': 'O',
            'replacement': 'x',
        }
        b_data = {'ttl': 30, 'value': b_value}
        b = NaptrRecord(self.zone, 'b', b_data)
        for k in a_values[0].keys():
            self.assertEquals(b_value[k], getattr(b.values[0], k))
        self.assertEquals(b_data, b.data)

        # missing value
        with self.assertRaises(Exception) as ctx:
            NaptrRecord(self.zone, None, {'ttl': 42})
        self.assertTrue('missing value' in ctx.exception.message)
        # invalid value
        with self.assertRaises(Exception) as ctx:
            NaptrRecord(self.zone, None, {'ttl': 42, 'value': {}})
        self.assertTrue('Invalid value' in ctx.exception.message)

        target = SimpleProvider()
        # No changes with self
        self.assertFalse(a.changes(a, target))
        # Diff in priority causes change
        other = NaptrRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].order = 22
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in replacement causes change
        other.values[0].order = a.values[0].order
        other.values[0].replacement = 'smtpX'
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)

        # full sorting
        # equivilent
        b_naptr_value = b.values[0]
        self.assertEquals(0, b_naptr_value.__cmp__(b_naptr_value))
        # by order
        self.assertEquals(1, b_naptr_value.__cmp__(NaptrValue({
            'order': 10,
            'preference': 31,
            'flags': 'M',
            'service': 'N',
            'regexp': 'O',
            'replacement': 'x',
        })))
        self.assertEquals(-1, b_naptr_value.__cmp__(NaptrValue({
            'order': 40,
            'preference': 31,
            'flags': 'M',
            'service': 'N',
            'regexp': 'O',
            'replacement': 'x',
        })))
        # by preference
        self.assertEquals(1, b_naptr_value.__cmp__(NaptrValue({
            'order': 30,
            'preference': 10,
            'flags': 'M',
            'service': 'N',
            'regexp': 'O',
            'replacement': 'x',
        })))
        self.assertEquals(-1, b_naptr_value.__cmp__(NaptrValue({
            'order': 30,
            'preference': 40,
            'flags': 'M',
            'service': 'N',
            'regexp': 'O',
            'replacement': 'x',
        })))
        # by flags
        self.assertEquals(1, b_naptr_value.__cmp__(NaptrValue({
            'order': 30,
            'preference': 31,
            'flags': 'A',
            'service': 'N',
            'regexp': 'O',
            'replacement': 'x',
        })))
        self.assertEquals(-1, b_naptr_value.__cmp__(NaptrValue({
            'order': 30,
            'preference': 31,
            'flags': 'Z',
            'service': 'N',
            'regexp': 'O',
            'replacement': 'x',
        })))
        # by service
        self.assertEquals(1, b_naptr_value.__cmp__(NaptrValue({
            'order': 30,
            'preference': 31,
            'flags': 'M',
            'service': 'A',
            'regexp': 'O',
            'replacement': 'x',
        })))
        self.assertEquals(-1, b_naptr_value.__cmp__(NaptrValue({
            'order': 30,
            'preference': 31,
            'flags': 'M',
            'service': 'Z',
            'regexp': 'O',
            'replacement': 'x',
        })))
        # by regexp
        self.assertEquals(1, b_naptr_value.__cmp__(NaptrValue({
            'order': 30,
            'preference': 31,
            'flags': 'M',
            'service': 'N',
            'regexp': 'A',
            'replacement': 'x',
        })))
        self.assertEquals(-1, b_naptr_value.__cmp__(NaptrValue({
            'order': 30,
            'preference': 31,
            'flags': 'M',
            'service': 'N',
            'regexp': 'Z',
            'replacement': 'x',
        })))
        # by replacement
        self.assertEquals(1, b_naptr_value.__cmp__(NaptrValue({
            'order': 30,
            'preference': 31,
            'flags': 'M',
            'service': 'N',
            'regexp': 'O',
            'replacement': 'a',
        })))
        self.assertEquals(-1, b_naptr_value.__cmp__(NaptrValue({
            'order': 30,
            'preference': 31,
            'flags': 'M',
            'service': 'N',
            'regexp': 'O',
            'replacement': 'z',
        })))

        # __repr__ doesn't blow up
        a.__repr__()

    def test_ns(self):
        a_values = ['5.6.7.8.', '6.7.8.9.', '7.8.9.0.']
        a_data = {'ttl': 30, 'values': a_values}
        a = NsRecord(self.zone, 'a', a_data)
        self.assertEquals('a', a.name)
        self.assertEquals('a.unit.tests.', a.fqdn)
        self.assertEquals(30, a.ttl)
        self.assertEquals(a_values, a.values)
        self.assertEquals(a_data, a.data)

        b_value = '9.8.7.6.'
        b_data = {'ttl': 30, 'value': b_value}
        b = NsRecord(self.zone, 'b', b_data)
        self.assertEquals([b_value], b.values)
        self.assertEquals(b_data, b.data)

        # missing values & value
        with self.assertRaises(Exception) as ctx:
            NsRecord(self.zone, None, {'ttl': 42})
        self.assertTrue('missing value(s)' in ctx.exception.message)

        with self.assertRaises(Exception) as ctx:
            NsRecord(self.zone, 'a', {
                'ttl': 30,
                'value': 'foo',
            })
        self.assertTrue('Invalid record' in ctx.exception.message)
        with self.assertRaises(Exception) as ctx:
            NsRecord(self.zone, 'a', {
                'ttl': 30,
                'values': ['foo.com.', 'bar.com'],
            })
        self.assertTrue('Invalid record' in ctx.exception.message)

    def test_ptr(self):
        self.assertSingleValue(PtrRecord, 'foo.bar.com.', 'other.bar.com.')
        with self.assertRaises(Exception) as ctx:
            PtrRecord(self.zone, 'a', {
                'ttl': 30,
                'value': 'foo',
            })
        self.assertTrue('Invalid record' in ctx.exception.message)

    def test_sshfp(self):
        a_values = [{
            'algorithm': 10,
            'fingerprint_type': 11,
            'fingerprint': 'abc123',
        }, {
            'algorithm': 20,
            'fingerprint_type': 21,
            'fingerprint': 'def456',
        }]
        a_data = {'ttl': 30, 'values': a_values}
        a = SshfpRecord(self.zone, 'a', a_data)
        self.assertEquals('a', a.name)
        self.assertEquals('a.unit.tests.', a.fqdn)
        self.assertEquals(30, a.ttl)
        self.assertEquals(a_values[0]['algorithm'], a.values[0].algorithm)
        self.assertEquals(a_values[0]['fingerprint_type'],
                          a.values[0].fingerprint_type)
        self.assertEquals(a_values[0]['fingerprint'], a.values[0].fingerprint)
        self.assertEquals(a_data, a.data)

        b_value = {
            'algorithm': 30,
            'fingerprint_type': 31,
            'fingerprint': 'ghi789',
        }
        b_data = {'ttl': 30, 'value': b_value}
        b = SshfpRecord(self.zone, 'b', b_data)
        self.assertEquals(b_value['algorithm'], b.values[0].algorithm)
        self.assertEquals(b_value['fingerprint_type'],
                          b.values[0].fingerprint_type)
        self.assertEquals(b_value['fingerprint'], b.values[0].fingerprint)
        self.assertEquals(b_data, b.data)

        # missing value
        with self.assertRaises(Exception) as ctx:
            SshfpRecord(self.zone, None, {'ttl': 42})
        self.assertTrue('missing value(s)' in ctx.exception.message)
        # invalid value
        with self.assertRaises(Exception) as ctx:
            SshfpRecord(self.zone, None, {'ttl': 42, 'value': {}})
        self.assertTrue('Invalid value' in ctx.exception.message)

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

    def test_spf(self):
        a_values = ['spf1 -all', 'spf1 -hrm']
        b_value = 'spf1 -other'
        self.assertMultipleValues(SpfRecord, a_values, b_value)

    def test_srv(self):
        a_values = [{
            'priority': 10,
            'weight': 11,
            'port': 12,
            'target': 'server1',
        }, {
            'priority': 20,
            'weight': 21,
            'port': 22,
            'target': 'server2',
        }]
        a_data = {'ttl': 30, 'values': a_values}
        a = SrvRecord(self.zone, '_a._tcp', a_data)
        self.assertEquals('_a._tcp', a.name)
        self.assertEquals('_a._tcp.unit.tests.', a.fqdn)
        self.assertEquals(30, a.ttl)
        self.assertEquals(a_values[0]['priority'], a.values[0].priority)
        self.assertEquals(a_values[0]['weight'], a.values[0].weight)
        self.assertEquals(a_values[0]['port'], a.values[0].port)
        self.assertEquals(a_values[0]['target'], a.values[0].target)
        self.assertEquals(a_data, a.data)

        b_value = {
            'priority': 30,
            'weight': 31,
            'port': 32,
            'target': 'server3',
        }
        b_data = {'ttl': 30, 'value': b_value}
        b = SrvRecord(self.zone, '_b._tcp', b_data)
        self.assertEquals(b_value['priority'], b.values[0].priority)
        self.assertEquals(b_value['weight'], b.values[0].weight)
        self.assertEquals(b_value['port'], b.values[0].port)
        self.assertEquals(b_value['target'], b.values[0].target)
        self.assertEquals(b_data, b.data)

        # invalid name
        with self.assertRaises(Exception) as ctx:
            SrvRecord(self.zone, 'bad', {'ttl': 42})
        self.assertEquals('Invalid name bad.unit.tests.',
                          ctx.exception.message)

        # missing value
        with self.assertRaises(Exception) as ctx:
            SrvRecord(self.zone, '_missing._tcp', {'ttl': 42})
        self.assertTrue('missing value(s)' in ctx.exception.message)
        # invalid value
        with self.assertRaises(Exception) as ctx:
            SrvRecord(self.zone, '_missing._udp', {'ttl': 42, 'value': {}})
        self.assertTrue('Invalid value' in ctx.exception.message)

        target = SimpleProvider()
        # No changes with self
        self.assertFalse(a.changes(a, target))
        # Diff in priority causes change
        other = SrvRecord(self.zone, '_a._icmp',
                          {'ttl': 30, 'values': a_values})
        other.values[0].priority = 22
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in weight causes change
        other.values[0].priority = a.values[0].priority
        other.values[0].weight = 33
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in port causes change
        other.values[0].weight = a.values[0].weight
        other.values[0].port = 44
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in target causes change
        other.values[0].port = a.values[0].port
        other.values[0].target = 'serverX'
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)

        # __repr__ doesn't blow up
        a.__repr__()

    def test_txt(self):
        a_values = ['a one', 'a two']
        b_value = 'b other'
        self.assertMultipleValues(TxtRecord, a_values, b_value)

        Record.new(self.zone, 'txt', {
            'ttl': 44,
            'type': 'TXT',
            'value': 'escaped\; foo',
        })

        with self.assertRaises(Exception) as ctx:
            Record.new(self.zone, 'txt', {
                'ttl': 44,
                'type': 'TXT',
                'value': 'un-escaped; foo',
            })
        self.assertEquals('Invalid record txt.unit.tests., unescaped ;',
                          ctx.exception.message)

    def test_record_new(self):
        txt = Record.new(self.zone, 'txt', {
            'ttl': 44,
            'type': 'TXT',
            'value': 'some text',
        })
        self.assertIsInstance(txt, TxtRecord)
        self.assertEquals('TXT', txt._type)
        self.assertEquals(['some text'], txt.values)

        # Missing type
        with self.assertRaises(Exception) as ctx:
            Record.new(self.zone, 'unknown', {})
        self.assertTrue('missing type' in ctx.exception.message)

        # Unkown type
        with self.assertRaises(Exception) as ctx:
            Record.new(self.zone, 'unknown', {
                'type': 'XXX',
            })
        self.assertTrue('Unknown record type' in ctx.exception.message)

    def test_change(self):
        existing = Record.new(self.zone, 'txt', {
            'ttl': 44,
            'type': 'TXT',
            'value': 'some text',
        })
        new = Record.new(self.zone, 'txt', {
            'ttl': 44,
            'type': 'TXT',
            'value': 'some change',
        })
        create = Create(new)
        self.assertEquals(new.values, create.record.values)
        update = Update(existing, new)
        self.assertEquals(new.values, update.record.values)
        delete = Delete(existing)
        self.assertEquals(existing.values, delete.record.values)

    def test_geo_value(self):
        code = 'NA-US-CA'
        values = ['1.2.3.4']
        geo = GeoValue(code, values)
        self.assertEquals(code, geo.code)
        self.assertEquals('NA', geo.continent_code)
        self.assertEquals('US', geo.country_code)
        self.assertEquals('CA', geo.subdivision_code)
        self.assertEquals(values, geo.values)
        self.assertEquals(['NA-US', 'NA'], list(geo.parents))
