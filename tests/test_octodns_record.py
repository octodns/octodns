#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from unittest import TestCase

from octodns.record import ARecord, AaaaRecord, AliasRecord, CaaRecord, \
    CnameRecord, Create, Delete, GeoValue, MxRecord, NaptrRecord, \
    NaptrValue, NsRecord, Record, SshfpRecord, SpfRecord, SrvRecord, \
    TxtRecord, Update, ValidationError
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

    def test_values_mixin_data(self):
        # no values, no value or values in data
        a = ARecord(self.zone, '', {
            'type': 'A',
            'ttl': 600,
            'values': []
        })
        self.assertNotIn('values', a.data)

        # empty value, no value or values in data
        b = ARecord(self.zone, '', {
            'type': 'A',
            'ttl': 600,
            'values': ['']
        })
        self.assertNotIn('value', b.data)

        # empty/None values, no value or values in data
        c = ARecord(self.zone, '', {
            'type': 'A',
            'ttl': 600,
            'values': ['', None]
        })
        self.assertNotIn('values', c.data)

        # empty/None values and valid, value in data
        c = ARecord(self.zone, '', {
            'type': 'A',
            'ttl': 600,
            'values': ['', None, '10.10.10.10']
        })
        self.assertNotIn('values', c.data)
        self.assertEqual('10.10.10.10', c.data['value'])

    def test_value_mixin_data(self):
        # unspecified value, no value in data
        a = AliasRecord(self.zone, '', {
            'type': 'ALIAS',
            'ttl': 600,
            'value': None
        })
        self.assertNotIn('value', a.data)

        # unspecified value, no value in data
        a = AliasRecord(self.zone, '', {
            'type': 'ALIAS',
            'ttl': 600,
            'value': ''
        })
        self.assertNotIn('value', a.data)

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

    def test_aaaa(self):
        a_values = ['2001:0db8:3c4d:0015:0000:0000:1a2f:1a2b',
                    '2001:0db8:3c4d:0015:0000:0000:1a2f:1a3b']
        b_value = '2001:0db8:3c4d:0015:0000:0000:1a2f:1a4b'
        self.assertMultipleValues(AaaaRecord, a_values, b_value)

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

    def test_alias(self):
        a_data = {'ttl': 0, 'value': 'www.unit.tests.'}
        a = AliasRecord(self.zone, '', a_data)
        self.assertEquals('', a.name)
        self.assertEquals('unit.tests.', a.fqdn)
        self.assertEquals(0, a.ttl)
        self.assertEquals(a_data['value'], a.value)
        self.assertEquals(a_data, a.data)

        target = SimpleProvider()
        # No changes with self
        self.assertFalse(a.changes(a, target))
        # Diff in value causes change
        other = AliasRecord(self.zone, 'a', a_data)
        other.value = 'foo.unit.tests.'
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)

        # __repr__ doesn't blow up
        a.__repr__()

    def test_caa(self):
        a_values = [{
            'flags': 0,
            'tag': 'issue',
            'value': 'ca.example.net',
        }, {
            'flags': 128,
            'tag': 'iodef',
            'value': 'mailto:security@example.com',
        }]
        a_data = {'ttl': 30, 'values': a_values}
        a = CaaRecord(self.zone, 'a', a_data)
        self.assertEquals('a', a.name)
        self.assertEquals('a.unit.tests.', a.fqdn)
        self.assertEquals(30, a.ttl)
        self.assertEquals(a_values[0]['flags'], a.values[0].flags)
        self.assertEquals(a_values[0]['tag'], a.values[0].tag)
        self.assertEquals(a_values[0]['value'], a.values[0].value)
        self.assertEquals(a_values[1]['flags'], a.values[1].flags)
        self.assertEquals(a_values[1]['tag'], a.values[1].tag)
        self.assertEquals(a_values[1]['value'], a.values[1].value)
        self.assertEquals(a_data, a.data)

        b_value = {
            'tag': 'iodef',
            'value': 'http://iodef.example.com/',
        }
        b_data = {'ttl': 30, 'value': b_value}
        b = CaaRecord(self.zone, 'b', b_data)
        self.assertEquals(0, b.values[0].flags)
        self.assertEquals(b_value['tag'], b.values[0].tag)
        self.assertEquals(b_value['value'], b.values[0].value)
        b_data['value']['flags'] = 0
        self.assertEquals(b_data, b.data)

        target = SimpleProvider()
        # No changes with self
        self.assertFalse(a.changes(a, target))
        # Diff in flags causes change
        other = CaaRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].flags = 128
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in tag causes change
        other.values[0].flags = a.values[0].flags
        other.values[0].tag = 'foo'
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in value causes change
        other.values[0].tag = a.values[0].tag
        other.values[0].value = 'bar'
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)

        # __repr__ doesn't blow up
        a.__repr__()

    def test_cname(self):
        self.assertSingleValue(CnameRecord, 'target.foo.com.',
                               'other.foo.com.')

    def test_mx(self):
        a_values = [{
            'preference': 10,
            'exchange': 'smtp1.'
        }, {
            'priority': 20,
            'value': 'smtp2.'
        }]
        a_data = {'ttl': 30, 'values': a_values}
        a = MxRecord(self.zone, 'a', a_data)
        self.assertEquals('a', a.name)
        self.assertEquals('a.unit.tests.', a.fqdn)
        self.assertEquals(30, a.ttl)
        self.assertEquals(a_values[0]['preference'], a.values[0].preference)
        self.assertEquals(a_values[0]['exchange'], a.values[0].exchange)
        self.assertEquals(a_values[1]['priority'], a.values[1].preference)
        self.assertEquals(a_values[1]['value'], a.values[1].exchange)
        a_data['values'][1] = {
            'preference': 20,
            'exchange': 'smtp2.',
        }
        self.assertEquals(a_data, a.data)

        b_value = {
            'preference': 0,
            'exchange': 'smtp3.',
        }
        b_data = {'ttl': 30, 'value': b_value}
        b = MxRecord(self.zone, 'b', b_data)
        self.assertEquals(b_value['preference'], b.values[0].preference)
        self.assertEquals(b_value['exchange'], b.values[0].exchange)
        self.assertEquals(b_data, b.data)

        target = SimpleProvider()
        # No changes with self
        self.assertFalse(a.changes(a, target))
        # Diff in preference causes change
        other = MxRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].preference = 22
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in value causes change
        other.values[0].preference = a.values[0].preference
        other.values[0].exchange = 'smtpX'
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
        # equivalent
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

        # Unknown type
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

    def test_healthcheck(self):
        new = Record.new(self.zone, 'a', {
            'ttl': 44,
            'type': 'A',
            'value': '1.2.3.4',
            'octodns': {
                'healthcheck': {
                    'path': '/_ready',
                    'host': 'bleep.bloop',
                    'protocol': 'HTTP',
                    'port': 8080,
                }
            }
        })
        self.assertEquals('/_ready', new.healthcheck_path)
        self.assertEquals('bleep.bloop', new.healthcheck_host)
        self.assertEquals('HTTP', new.healthcheck_protocol)
        self.assertEquals(8080, new.healthcheck_port)

        new = Record.new(self.zone, 'a', {
            'ttl': 44,
            'type': 'A',
            'value': '1.2.3.4',
        })
        self.assertEquals('/_dns', new.healthcheck_path)
        self.assertEquals('a.unit.tests', new.healthcheck_host)
        self.assertEquals('HTTPS', new.healthcheck_protocol)
        self.assertEquals(443, new.healthcheck_port)

    def test_inored(self):
        new = Record.new(self.zone, 'txt', {
            'ttl': 44,
            'type': 'TXT',
            'value': 'some change',
            'octodns': {
                'ignored': True,
            }
        })
        self.assertTrue(new.ignored)
        new = Record.new(self.zone, 'txt', {
            'ttl': 44,
            'type': 'TXT',
            'value': 'some change',
            'octodns': {
                'ignored': False,
            }
        })
        self.assertFalse(new.ignored)
        new = Record.new(self.zone, 'txt', {
            'ttl': 44,
            'type': 'TXT',
            'value': 'some change',
        })
        self.assertFalse(new.ignored)


class TestRecordValidation(TestCase):
    zone = Zone('unit.tests.', [])

    def test_base(self):
        # no ttl
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'A',
                'value': '1.2.3.4',
            })
        self.assertEquals(['missing ttl'], ctx.exception.reasons)

        # invalid ttl
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'A',
                'ttl': -1,
                'value': '1.2.3.4',
            })
        self.assertEquals('www.unit.tests.', ctx.exception.fqdn)
        self.assertEquals(['invalid ttl'], ctx.exception.reasons)

        # no exception if we're in lenient mode
        Record.new(self.zone, 'www', {
            'type': 'A',
            'ttl': -1,
            'value': '1.2.3.4',
        }, lenient=True)

        # __init__ may still blow up, even if validation is lenient
        with self.assertRaises(KeyError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'A',
                'ttl': -1,
            }, lenient=True)
        self.assertEquals(('value',), ctx.exception.args)

        # no exception if we're in lenient mode from config
        Record.new(self.zone, 'www', {
            'octodns': {
                'lenient': True
            },
            'type': 'A',
            'ttl': -1,
            'value': '1.2.3.4',
        }, lenient=True)

    def test_A_and_values_mixin(self):
        # doesn't blow up
        Record.new(self.zone, '', {
            'type': 'A',
            'ttl': 600,
            'value': '1.2.3.4',
        })
        Record.new(self.zone, '', {
            'type': 'A',
            'ttl': 600,
            'values': [
                '1.2.3.4',
            ]
        })
        Record.new(self.zone, '', {
            'type': 'A',
            'ttl': 600,
            'values': [
                '1.2.3.4',
                '1.2.3.5',
            ]
        })

        # missing value(s), no value or value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'A',
                'ttl': 600,
            })
        self.assertEquals(['missing value(s)'], ctx.exception.reasons)

        # missing value(s), empty values
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'A',
                'ttl': 600,
                'values': []
            })
        self.assertEquals(['missing value(s)'], ctx.exception.reasons)

        # missing value(s), None values
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'A',
                'ttl': 600,
                'values': None
            })
        self.assertEquals(['missing value(s)'], ctx.exception.reasons)

        # missing value(s) and empty value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'A',
                'ttl': 600,
                'values': [None, '']
            })
        self.assertEquals(['missing value(s)',
                           'empty value'], ctx.exception.reasons)

        # missing value(s), None value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'A',
                'ttl': 600,
                'value': None
            })
        self.assertEquals(['missing value(s)'], ctx.exception.reasons)

        # empty value, empty string value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'A',
                'ttl': 600,
                'value': ''
            })
        self.assertEquals(['empty value'], ctx.exception.reasons)

        # missing value(s) & ttl
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'A',
            })
        self.assertEquals(['missing ttl', 'missing value(s)'],
                          ctx.exception.reasons)

        # invalid ip address
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'A',
                'ttl': 600,
                'value': 'hello'
            })
        self.assertEquals(['invalid ip address "hello"'],
                          ctx.exception.reasons)

        # invalid ip addresses
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'A',
                'ttl': 600,
                'values': ['hello', 'goodbye']
            })
        self.assertEquals([
            'invalid ip address "hello"',
            'invalid ip address "goodbye"'
        ], ctx.exception.reasons)

        # invalid & valid ip addresses, no ttl
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'A',
                'values': ['1.2.3.4', 'hello', '5.6.7.8']
            })
        self.assertEquals([
            'missing ttl',
            'invalid ip address "hello"',
        ], ctx.exception.reasons)

    def test_geo(self):
        Record.new(self.zone, '', {
            'geo': {
                'NA': ['1.2.3.5'],
                'NA-US': ['1.2.3.5', '1.2.3.6']
            },
            'type': 'A',
            'ttl': 600,
            'value': '1.2.3.4',
        })

        # invalid ip address
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'geo': {
                    'NA': ['hello'],
                    'NA-US': ['1.2.3.5', '1.2.3.6']
                },
                'type': 'A',
                'ttl': 600,
                'value': '1.2.3.4',
            })
        self.assertEquals(['invalid ip address "hello"'],
                          ctx.exception.reasons)

        # invalid geo code
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'geo': {
                    'XYZ': ['1.2.3.4'],
                },
                'type': 'A',
                'ttl': 600,
                'value': '1.2.3.4',
            })
        self.assertEquals(['invalid geo "XYZ"'], ctx.exception.reasons)

        # invalid ip address
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'geo': {
                    'NA': ['hello'],
                    'NA-US': ['1.2.3.5', 'goodbye']
                },
                'type': 'A',
                'ttl': 600,
                'value': '1.2.3.4',
            })
        self.assertEquals([
            'invalid ip address "hello"',
            'invalid ip address "goodbye"'
        ], ctx.exception.reasons)

        # invalid healthcheck protocol
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'a', {
                'geo': {
                    'NA': ['1.2.3.5'],
                    'NA-US': ['1.2.3.5', '1.2.3.6']
                },
                'type': 'A',
                'ttl': 600,
                'value': '1.2.3.4',
                'octodns': {
                    'healthcheck': {
                        'protocol': 'FTP',
                    }
                }
            })
        self.assertEquals(['invalid healthcheck protocol'],
                          ctx.exception.reasons)

    def test_AAAA(self):
        # doesn't blow up
        Record.new(self.zone, '', {
            'type': 'AAAA',
            'ttl': 600,
            'value': '2601:644:500:e210:62f8:1dff:feb8:947a',
        })
        Record.new(self.zone, '', {
            'type': 'AAAA',
            'ttl': 600,
            'values': [
                '2601:644:500:e210:62f8:1dff:feb8:947a',
                '2601:644:500:e210:62f8:1dff:feb8:947b',
            ]
        })

        # invalid ip address
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'AAAA',
                'ttl': 600,
                'value': 'hello'
            })
        self.assertEquals(['invalid ip address "hello"'],
                          ctx.exception.reasons)
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'AAAA',
                'ttl': 600,
                'value': '1.2.3.4'
            })
        self.assertEquals(['invalid ip address "1.2.3.4"'],
                          ctx.exception.reasons)

        # invalid ip addresses
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'AAAA',
                'ttl': 600,
                'values': ['hello', 'goodbye']
            })
        self.assertEquals([
            'invalid ip address "hello"',
            'invalid ip address "goodbye"'
        ], ctx.exception.reasons)

    def test_ALIAS_and_value_mixin(self):
        # doesn't blow up
        Record.new(self.zone, '', {
            'type': 'ALIAS',
            'ttl': 600,
            'value': 'foo.bar.com.',
        })

        # missing value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'ALIAS',
                'ttl': 600,
            })
        self.assertEquals(['missing value'], ctx.exception.reasons)

        # missing value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'ALIAS',
                'ttl': 600,
                'value': None
            })
        self.assertEquals(['missing value'], ctx.exception.reasons)

        # empty value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'ALIAS',
                'ttl': 600,
                'value': ''
            })
        self.assertEquals(['empty value'], ctx.exception.reasons)

        # missing trailing .
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'ALIAS',
                'ttl': 600,
                'value': 'foo.bar.com',
            })
        self.assertEquals(['missing trailing .'], ctx.exception.reasons)

    def test_CAA(self):
        # doesn't blow up
        Record.new(self.zone, '', {
            'type': 'CAA',
            'ttl': 600,
            'value': {
                'flags': 128,
                'tag': 'iodef',
                'value': 'http://foo.bar.com/'
            }
        })

        # invalid flags
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'CAA',
                'ttl': 600,
                'value': {
                    'flags': -42,
                    'tag': 'iodef',
                    'value': 'http://foo.bar.com/',
                }
            })
        self.assertEquals(['invalid flags "-42"'], ctx.exception.reasons)
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'CAA',
                'ttl': 600,
                'value': {
                    'flags': 442,
                    'tag': 'iodef',
                    'value': 'http://foo.bar.com/',
                }
            })
        self.assertEquals(['invalid flags "442"'], ctx.exception.reasons)
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'CAA',
                'ttl': 600,
                'value': {
                    'flags': 'nope',
                    'tag': 'iodef',
                    'value': 'http://foo.bar.com/',
                }
            })
        self.assertEquals(['invalid flags "nope"'], ctx.exception.reasons)

        # missing tag
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'CAA',
                'ttl': 600,
                'value': {
                    'value': 'http://foo.bar.com/',
                }
            })
        self.assertEquals(['missing tag'], ctx.exception.reasons)

        # missing value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'CAA',
                'ttl': 600,
                'value': {
                    'tag': 'iodef',
                }
            })
        self.assertEquals(['missing value'], ctx.exception.reasons)

    def test_CNAME(self):
        # doesn't blow up
        Record.new(self.zone, 'www', {
            'type': 'CNAME',
            'ttl': 600,
            'value': 'foo.bar.com.',
        })

        # root cname is a no-no
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'CNAME',
                'ttl': 600,
                'value': 'foo.bar.com.',
            })
        self.assertEquals(['root CNAME not allowed'], ctx.exception.reasons)

        # missing trailing .
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'CNAME',
                'ttl': 600,
                'value': 'foo.bar.com',
            })
        self.assertEquals(['missing trailing .'], ctx.exception.reasons)

    def test_MX(self):
        # doesn't blow up
        Record.new(self.zone, '', {
            'type': 'MX',
            'ttl': 600,
            'value': {
                'preference': 10,
                'exchange': 'foo.bar.com.'
            }
        })

        # missing preference
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'MX',
                'ttl': 600,
                'value': {
                    'exchange': 'foo.bar.com.'
                }
            })
        self.assertEquals(['missing preference'], ctx.exception.reasons)

        # invalid preference
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'MX',
                'ttl': 600,
                'value': {
                    'preference': 'nope',
                    'exchange': 'foo.bar.com.'
                }
            })
        self.assertEquals(['invalid preference "nope"'], ctx.exception.reasons)

        # missing exchange
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'MX',
                'ttl': 600,
                'value': {
                    'preference': 10,
                }
            })
        self.assertEquals(['missing exchange'], ctx.exception.reasons)

        # missing trailing .
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'MX',
                'ttl': 600,
                'value': {
                    'preference': 10,
                    'exchange': 'foo.bar.com'
                }
            })
        self.assertEquals(['missing trailing .'], ctx.exception.reasons)

    def test_NXPTR(self):
        # doesn't blow up
        Record.new(self.zone, '', {
            'type': 'NAPTR',
            'ttl': 600,
            'value': {
                'order': 10,
                'preference': 20,
                'flags': 'S',
                'service': 'srv',
                'regexp': '.*',
                'replacement': '.'
            }
        })

        # missing X priority
        value = {
            'order': 10,
            'preference': 20,
            'flags': 'S',
            'service': 'srv',
            'regexp': '.*',
            'replacement': '.'
        }
        for k in ('order', 'preference', 'flags', 'service', 'regexp',
                  'replacement'):
            v = dict(value)
            del v[k]
            with self.assertRaises(ValidationError) as ctx:
                Record.new(self.zone, '', {
                    'type': 'NAPTR',
                    'ttl': 600,
                    'value': v
                })
            self.assertEquals(['missing {}'.format(k)], ctx.exception.reasons)

        # non-int order
        v = dict(value)
        v['order'] = 'boo'
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'NAPTR',
                'ttl': 600,
                'value': v
            })
        self.assertEquals(['invalid order "boo"'], ctx.exception.reasons)

        # non-int preference
        v = dict(value)
        v['preference'] = 'who'
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'NAPTR',
                'ttl': 600,
                'value': v
            })
        self.assertEquals(['invalid preference "who"'], ctx.exception.reasons)

        # unrecognized flags
        v = dict(value)
        v['flags'] = 'X'
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'NAPTR',
                'ttl': 600,
                'value': v
            })
        self.assertEquals(['unrecognized flags "X"'], ctx.exception.reasons)

    def test_NS(self):
        # doesn't blow up
        Record.new(self.zone, '', {
            'type': 'NS',
            'ttl': 600,
            'values': [
                'foo.bar.com.',
                '1.2.3.4.'
            ]
        })

        # missing value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'NS',
                'ttl': 600,
            })
        self.assertEquals(['missing value(s)'], ctx.exception.reasons)

        # no trailing .
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'NS',
                'ttl': 600,
                'value': 'foo.bar',
            })
        self.assertEquals(['missing trailing .'], ctx.exception.reasons)

    def test_PTR(self):
        # doesn't blow up (name & zone here don't make any sense, but not
        # important)
        Record.new(self.zone, '', {
            'type': 'PTR',
            'ttl': 600,
            'value': 'foo.bar.com.',
        })

        # missing value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'PTR',
                'ttl': 600,
            })
        self.assertEquals(['missing value'], ctx.exception.reasons)

        # no trailing .
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'PTR',
                'ttl': 600,
                'value': 'foo.bar',
            })
        self.assertEquals(['missing trailing .'], ctx.exception.reasons)

    def test_SSHFP(self):
        # doesn't blow up
        Record.new(self.zone, '', {
            'type': 'SSHFP',
            'ttl': 600,
            'value': {
                'algorithm': 1,
                'fingerprint_type': 1,
                'fingerprint': 'bf6b6825d2977c511a475bbefb88aad54a92ac73'
            }
        })

        # missing algorithm
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'SSHFP',
                'ttl': 600,
                'value': {
                    'fingerprint_type': 1,
                    'fingerprint': 'bf6b6825d2977c511a475bbefb88aad54a92ac73'
                }
            })
        self.assertEquals(['missing algorithm'], ctx.exception.reasons)

        # invalid algorithm
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'SSHFP',
                'ttl': 600,
                'value': {
                    'algorithm': 'nope',
                    'fingerprint_type': 2,
                    'fingerprint': 'bf6b6825d2977c511a475bbefb88aad54a92ac73'
                }
            })
        self.assertEquals(['invalid algorithm "nope"'], ctx.exception.reasons)

        # unrecognized algorithm
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'SSHFP',
                'ttl': 600,
                'value': {
                    'algorithm': 42,
                    'fingerprint_type': 1,
                    'fingerprint': 'bf6b6825d2977c511a475bbefb88aad54a92ac73'
                }
            })
        self.assertEquals(['unrecognized algorithm "42"'],
                          ctx.exception.reasons)

        # missing fingerprint_type
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'SSHFP',
                'ttl': 600,
                'value': {
                    'algorithm': 2,
                    'fingerprint': 'bf6b6825d2977c511a475bbefb88aad54a92ac73'
                }
            })
        self.assertEquals(['missing fingerprint_type'], ctx.exception.reasons)

        # invalid fingerprint_type
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'SSHFP',
                'ttl': 600,
                'value': {
                    'algorithm': 3,
                    'fingerprint_type': 'yeeah',
                    'fingerprint': 'bf6b6825d2977c511a475bbefb88aad54a92ac73'
                }
            })
        self.assertEquals(['invalid fingerprint_type "yeeah"'],
                          ctx.exception.reasons)

        # unrecognized fingerprint_type
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'SSHFP',
                'ttl': 600,
                'value': {
                    'algorithm': 1,
                    'fingerprint_type': 42,
                    'fingerprint': 'bf6b6825d2977c511a475bbefb88aad54a92ac73'
                }
            })
        self.assertEquals(['unrecognized fingerprint_type "42"'],
                          ctx.exception.reasons)

        # missing fingerprint
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'SSHFP',
                'ttl': 600,
                'value': {
                    'algorithm': 1,
                    'fingerprint_type': 1,
                }
            })
        self.assertEquals(['missing fingerprint'], ctx.exception.reasons)

    def test_SPF(self):
        # doesn't blow up (name & zone here don't make any sense, but not
        # important)
        Record.new(self.zone, '', {
            'type': 'SPF',
            'ttl': 600,
            'values': [
                'v=spf1 ip4:192.168.0.1/16-all',
                'v=spf1 ip4:10.1.2.1/24-all',
                'this has some\\; semi-colons\\; in it',
            ]
        })

        # missing value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'SPF',
                'ttl': 600,
            })
        self.assertEquals(['missing value(s)'], ctx.exception.reasons)

        # missing escapes
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'SPF',
                'ttl': 600,
                'value': 'this has some; semi-colons\\; in it',
            })
        self.assertEquals(['unescaped ;'], ctx.exception.reasons)

    def test_SRV(self):
        # doesn't blow up
        Record.new(self.zone, '_srv._tcp', {
            'type': 'SRV',
            'ttl': 600,
            'value': {
                'priority': 1,
                'weight': 2,
                'port': 3,
                'target': 'foo.bar.baz.'
            }
        })

        # invalid name
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'neup', {
                'type': 'SRV',
                'ttl': 600,
                'value': {
                    'priority': 1,
                    'weight': 2,
                    'port': 3,
                    'target': 'foo.bar.baz.'
                }
            })
        self.assertEquals(['invalid name'], ctx.exception.reasons)

        # missing priority
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '_srv._tcp', {
                'type': 'SRV',
                'ttl': 600,
                'value': {
                    'weight': 2,
                    'port': 3,
                    'target': 'foo.bar.baz.'
                }
            })
        self.assertEquals(['missing priority'], ctx.exception.reasons)

        # invalid priority
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '_srv._tcp', {
                'type': 'SRV',
                'ttl': 600,
                'value': {
                    'priority': 'foo',
                    'weight': 2,
                    'port': 3,
                    'target': 'foo.bar.baz.'
                }
            })
        self.assertEquals(['invalid priority "foo"'], ctx.exception.reasons)

        # missing weight
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '_srv._tcp', {
                'type': 'SRV',
                'ttl': 600,
                'value': {
                    'priority': 1,
                    'port': 3,
                    'target': 'foo.bar.baz.'
                }
            })
        self.assertEquals(['missing weight'], ctx.exception.reasons)
        # invalid weight
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '_srv._tcp', {
                'type': 'SRV',
                'ttl': 600,
                'value': {
                    'priority': 1,
                    'weight': 'foo',
                    'port': 3,
                    'target': 'foo.bar.baz.'
                }
            })
        self.assertEquals(['invalid weight "foo"'], ctx.exception.reasons)

        # missing port
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '_srv._tcp', {
                'type': 'SRV',
                'ttl': 600,
                'value': {
                    'priority': 1,
                    'weight': 2,
                    'target': 'foo.bar.baz.'
                }
            })
        self.assertEquals(['missing port'], ctx.exception.reasons)
        # invalid port
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '_srv._tcp', {
                'type': 'SRV',
                'ttl': 600,
                'value': {
                    'priority': 1,
                    'weight': 2,
                    'port': 'foo',
                    'target': 'foo.bar.baz.'
                }
            })
        self.assertEquals(['invalid port "foo"'], ctx.exception.reasons)

        # missing target
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '_srv._tcp', {
                'type': 'SRV',
                'ttl': 600,
                'value': {
                    'priority': 1,
                    'weight': 2,
                    'port': 3,
                }
            })
        self.assertEquals(['missing target'], ctx.exception.reasons)
        # invalid target
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '_srv._tcp', {
                'type': 'SRV',
                'ttl': 600,
                'value': {
                    'priority': 1,
                    'weight': 2,
                    'port': 3,
                    'target': 'foo.bar.baz'
                }
            })
        self.assertEquals(['missing trailing .'],
                          ctx.exception.reasons)

    def test_TXT(self):
        # doesn't blow up (name & zone here don't make any sense, but not
        # important)
        Record.new(self.zone, '', {
            'type': 'TXT',
            'ttl': 600,
            'values': [
                'hello world',
                'this has some\\; semi-colons\\; in it',
            ]
        })

        # missing value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'TXT',
                'ttl': 600,
            })
        self.assertEquals(['missing value(s)'], ctx.exception.reasons)

        # missing escapes
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'TXT',
                'ttl': 600,
                'value': 'this has some; semi-colons\\; in it',
            })
        self.assertEquals(['unescaped ;'], ctx.exception.reasons)

    def test_TXT_long_value_chunking(self):
        expected = '"Lorem ipsum dolor sit amet, consectetur adipiscing ' \
            'elit, sed do eiusmod tempor incididunt ut labore et dolore ' \
            'magna aliqua. Ut enim ad minim veniam, quis nostrud ' \
            'exercitation ullamco laboris nisi ut aliquip ex ea commodo ' \
            'consequat. Duis aute irure dolor i" "n reprehenderit in ' \
            'voluptate velit esse cillum dolore eu fugiat nulla pariatur. ' \
            'Excepteur sint occaecat cupidatat non proident, sunt in culpa ' \
            'qui officia deserunt mollit anim id est laborum."'

        long_value = 'Lorem ipsum dolor sit amet, consectetur adipiscing ' \
            'elit, sed do eiusmod tempor incididunt ut labore et dolore ' \
            'magna aliqua. Ut enim ad minim veniam, quis nostrud ' \
            'exercitation ullamco laboris nisi ut aliquip ex ea commodo ' \
            'consequat. Duis aute irure dolor in reprehenderit in ' \
            'voluptate velit esse cillum dolore eu fugiat nulla ' \
            'pariatur. Excepteur sint occaecat cupidatat non proident, ' \
            'sunt in culpa qui officia deserunt mollit anim id est ' \
            'laborum.'
        # Single string
        single = Record.new(self.zone, '', {
            'type': 'TXT',
            'ttl': 600,
            'values': [
                'hello world',
                long_value,
                'this has some\\; semi-colons\\; in it',
            ]
        })
        self.assertEquals(3, len(single.values))
        self.assertEquals(3, len(single.chunked_values))
        # Note we are checking that this normalizes the chunking, not that we
        # get out what we put in.
        self.assertEquals(expected, single.chunked_values[0])

        long_split_value = '"Lorem ipsum dolor sit amet, consectetur ' \
            'adipiscing elit, sed do eiusmod tempor incididunt ut ' \
            'labore et dolore magna aliqua. Ut enim ad minim veniam, ' \
            'quis nostrud exercitation ullamco laboris nisi ut aliquip ' \
            'ex" " ea commodo consequat. Duis aute irure dolor in ' \
            'reprehenderit in voluptate velit esse cillum dolore eu ' \
            'fugiat nulla pariatur. Excepteur sint occaecat cupidatat ' \
            'non proident, sunt in culpa qui officia deserunt mollit ' \
            'anim id est laborum."'
        # Chunked
        chunked = Record.new(self.zone, '', {
            'type': 'TXT',
            'ttl': 600,
            'values': [
                '"hello world"',
                long_split_value,
                '"this has some\\; semi-colons\\; in it"',
            ]
        })
        self.assertEquals(expected, chunked.chunked_values[0])
        # should be single values, no quoting
        self.assertEquals(single.values, chunked.values)
        # should be chunked values, with quoting
        self.assertEquals(single.chunked_values, chunked.chunked_values)
