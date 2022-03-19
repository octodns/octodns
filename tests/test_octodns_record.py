#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from unittest import TestCase

from octodns.record import ARecord, AaaaRecord, AliasRecord, CaaRecord, \
    CaaValue, CnameRecord, DnameRecord, Create, Delete, GeoValue, LocRecord, \
    LocValue, MxRecord, MxValue, NaptrRecord, NaptrValue, NsRecord, \
    PtrRecord, Record, RecordException, SshfpRecord, SshfpValue, SpfRecord, \
    SrvRecord, SrvValue, TxtRecord, Update, UrlfwdRecord, UrlfwdValue, \
    ValidationError, _Dynamic, _DynamicPool, _DynamicRule, _NsValue, \
    ValuesMixin
from octodns.zone import Zone

from helpers import DynamicProvider, GeoProvider, SimpleProvider


class TestRecord(TestCase):
    zone = Zone('unit.tests.', [])

    def test_registration(self):
        with self.assertRaises(RecordException) as ctx:
            Record.register_type(None, 'A')
        self.assertEqual('Type "A" already registered by '
                         'octodns.record.ARecord', str(ctx.exception))

        class AaRecord(ValuesMixin, Record):
            _type = 'AA'
            _value_type = _NsValue

        Record.register_type(AaRecord)
        aa = Record.new(self.zone, 'registered', {
            'ttl': 360,
            'type': 'AA',
            'value': 'does.not.matter.',
        })
        self.assertEqual(AaRecord, aa.__class__)

    def test_lowering(self):
        record = ARecord(self.zone, 'MiXeDcAsE', {
            'ttl': 30,
            'type': 'A',
            'value': '1.2.3.4',
        })
        self.assertEqual('mixedcase', record.name)

    def test_alias_lowering_value(self):
        upper_record = AliasRecord(self.zone, 'aliasUppwerValue', {
            'ttl': 30,
            'type': 'ALIAS',
            'value': 'GITHUB.COM',
        })
        lower_record = AliasRecord(self.zone, 'aliasLowerValue', {
            'ttl': 30,
            'type': 'ALIAS',
            'value': 'github.com',
        })
        self.assertEqual(upper_record.value, lower_record.value)

    def test_cname_lowering_value(self):
        upper_record = CnameRecord(self.zone, 'CnameUppwerValue', {
            'ttl': 30,
            'type': 'CNAME',
            'value': 'GITHUB.COM',
        })
        lower_record = CnameRecord(self.zone, 'CnameLowerValue', {
            'ttl': 30,
            'type': 'CNAME',
            'value': 'github.com',
        })
        self.assertEqual(upper_record.value, lower_record.value)

    def test_dname_lowering_value(self):
        upper_record = DnameRecord(self.zone, 'DnameUppwerValue', {
            'ttl': 30,
            'type': 'DNAME',
            'value': 'GITHUB.COM',
        })
        lower_record = DnameRecord(self.zone, 'DnameLowerValue', {
            'ttl': 30,
            'type': 'DNAME',
            'value': 'github.com',
        })
        self.assertEqual(upper_record.value, lower_record.value)

    def test_ptr_lowering_value(self):
        upper_record = PtrRecord(self.zone, 'PtrUppwerValue', {
            'ttl': 30,
            'type': 'PTR',
            'value': 'GITHUB.COM',
        })
        lower_record = PtrRecord(self.zone, 'PtrLowerValue', {
            'ttl': 30,
            'type': 'PTR',
            'value': 'github.com',
        })
        self.assertEqual(upper_record.value, lower_record.value)

    def test_a_and_record(self):
        a_values = ['1.2.3.4', '2.2.3.4']
        a_data = {'ttl': 30, 'values': a_values}
        a = ARecord(self.zone, 'a', a_data)
        self.assertEqual('a', a.name)
        self.assertEqual('a.unit.tests.', a.fqdn)
        self.assertEqual(30, a.ttl)
        self.assertEqual(a_values, a.values)
        self.assertEqual(a_data, a.data)

        b_value = '3.2.3.4'
        b_data = {'ttl': 30, 'value': b_value}
        b = ARecord(self.zone, 'b', b_data)
        self.assertEqual([b_value], b.values)
        self.assertEqual(b_data, b.data)

        # top-level
        data = {'ttl': 30, 'value': '4.2.3.4'}
        self.assertEqual(self.zone.name, ARecord(self.zone, '', data).fqdn)
        self.assertEqual(self.zone.name, ARecord(self.zone, None, data).fqdn)

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
        self.assertEqual(a, update.existing)
        self.assertEqual(other, update.new)
        # changes if values modified
        other.ttl = a.ttl
        other.values = ['4.4.4.4']
        update = a.changes(other, target)
        self.assertEqual(a, update.existing)
        self.assertEqual(other, update.new)

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
        self.assertEqual(geo_data, geo.data)

        other_data = {'ttl': 42, 'values': ['5.2.3.4', '6.2.3.4'],
                      'geo': {'AF': ['1.1.1.1'],
                              'AS-JP': ['2.2.2.2', '3.3.3.3'],
                              'NA-US': ['4.4.4.4', '5.5.5.5'],
                              'NA-US-CA': ['6.6.6.6', '7.7.7.7']}}
        other = ARecord(self.zone, 'geo', other_data)
        self.assertEqual(other_data, other.data)

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
        self.assertEqual('a', a.name)
        self.assertEqual('a.unit.tests.', a.fqdn)
        self.assertEqual(30, a.ttl)
        self.assertEqual(a_values, a.values)
        self.assertEqual(a_data, a.data)

        b_data = {'ttl': 30, 'value': b_value}
        b = _type(self.zone, 'b', b_data)
        self.assertEqual([b_value], b.values)
        self.assertEqual(b_data, b.data)

    def test_aaaa(self):
        a_values = ['2001:db8:3c4d:15::1a2f:1a2b',
                    '2001:db8:3c4d:15::1a2f:1a3b']
        b_value = '2001:db8:3c4d:15::1a2f:1a4b'
        self.assertMultipleValues(AaaaRecord, a_values, b_value)

        # Specifically validate that we normalize IPv6 addresses
        values = ['2001:db8:3c4d:15:0000:0000:1a2f:1a2b',
                  '2001:0db8:3c4d:0015::1a2f:1a3b']
        data = {
            'ttl': 30,
            'values': values,
        }
        record = AaaaRecord(self.zone, 'aaaa', data)
        self.assertEqual(a_values, record.values)

    def assertSingleValue(self, _type, a_value, b_value):
        a_data = {'ttl': 30, 'value': a_value}
        a = _type(self.zone, 'a', a_data)
        self.assertEqual('a', a.name)
        self.assertEqual('a.unit.tests.', a.fqdn)
        self.assertEqual(30, a.ttl)
        self.assertEqual(a_value, a.value)
        self.assertEqual(a_data, a.data)

        b_data = {'ttl': 30, 'value': b_value}
        b = _type(self.zone, 'b', b_data)
        self.assertEqual(b_value, b.value)
        self.assertEqual(b_data, b.data)

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
        self.assertEqual('', a.name)
        self.assertEqual('unit.tests.', a.fqdn)
        self.assertEqual(0, a.ttl)
        self.assertEqual(a_data['value'], a.value)
        self.assertEqual(a_data, a.data)

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
        self.assertEqual('a', a.name)
        self.assertEqual('a.unit.tests.', a.fqdn)
        self.assertEqual(30, a.ttl)
        self.assertEqual(a_values[0]['flags'], a.values[0].flags)
        self.assertEqual(a_values[0]['tag'], a.values[0].tag)
        self.assertEqual(a_values[0]['value'], a.values[0].value)
        self.assertEqual(a_values[1]['flags'], a.values[1].flags)
        self.assertEqual(a_values[1]['tag'], a.values[1].tag)
        self.assertEqual(a_values[1]['value'], a.values[1].value)
        self.assertEqual(a_data, a.data)

        b_value = {
            'tag': 'iodef',
            'value': 'http://iodef.example.com/',
        }
        b_data = {'ttl': 30, 'value': b_value}
        b = CaaRecord(self.zone, 'b', b_data)
        self.assertEqual(0, b.values[0].flags)
        self.assertEqual(b_value['tag'], b.values[0].tag)
        self.assertEqual(b_value['value'], b.values[0].value)
        b_data['value']['flags'] = 0
        self.assertEqual(b_data, b.data)

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

    def test_dname(self):
        self.assertSingleValue(DnameRecord, 'target.foo.com.',
                               'other.foo.com.')

    def test_loc(self):
        a_values = [{
            'lat_degrees': 31,
            'lat_minutes': 58,
            'lat_seconds': 52.1,
            'lat_direction': 'S',
            'long_degrees': 115,
            'long_minutes': 49,
            'long_seconds': 11.7,
            'long_direction': 'E',
            'altitude': 20,
            'size': 10,
            'precision_horz': 10,
            'precision_vert': 2,
        }]
        a_data = {'ttl': 30, 'values': a_values}
        a = LocRecord(self.zone, 'a', a_data)
        self.assertEqual('a', a.name)
        self.assertEqual('a.unit.tests.', a.fqdn)
        self.assertEqual(30, a.ttl)
        self.assertEqual(a_values[0]['lat_degrees'], a.values[0].lat_degrees)
        self.assertEqual(a_values[0]['lat_minutes'], a.values[0].lat_minutes)
        self.assertEqual(a_values[0]['lat_seconds'], a.values[0].lat_seconds)
        self.assertEqual(a_values[0]['lat_direction'],
                         a.values[0].lat_direction)
        self.assertEqual(a_values[0]['long_degrees'],
                         a.values[0].long_degrees)
        self.assertEqual(a_values[0]['long_minutes'],
                         a.values[0].long_minutes)
        self.assertEqual(a_values[0]['long_seconds'],
                         a.values[0].long_seconds)
        self.assertEqual(a_values[0]['long_direction'],
                         a.values[0].long_direction)
        self.assertEqual(a_values[0]['altitude'], a.values[0].altitude)
        self.assertEqual(a_values[0]['size'], a.values[0].size)
        self.assertEqual(a_values[0]['precision_horz'],
                         a.values[0].precision_horz)
        self.assertEqual(a_values[0]['precision_vert'],
                         a.values[0].precision_vert)

        b_value = {
            'lat_degrees': 32,
            'lat_minutes': 7,
            'lat_seconds': 19,
            'lat_direction': 'S',
            'long_degrees': 116,
            'long_minutes': 2,
            'long_seconds': 25,
            'long_direction': 'E',
            'altitude': 10,
            'size': 1,
            'precision_horz': 10000,
            'precision_vert': 10,
        }
        b_data = {'ttl': 30, 'value': b_value}
        b = LocRecord(self.zone, 'b', b_data)
        self.assertEqual(b_value['lat_degrees'], b.values[0].lat_degrees)
        self.assertEqual(b_value['lat_minutes'], b.values[0].lat_minutes)
        self.assertEqual(b_value['lat_seconds'], b.values[0].lat_seconds)
        self.assertEqual(b_value['lat_direction'], b.values[0].lat_direction)
        self.assertEqual(b_value['long_degrees'], b.values[0].long_degrees)
        self.assertEqual(b_value['long_minutes'], b.values[0].long_minutes)
        self.assertEqual(b_value['long_seconds'], b.values[0].long_seconds)
        self.assertEqual(b_value['long_direction'],
                         b.values[0].long_direction)
        self.assertEqual(b_value['altitude'], b.values[0].altitude)
        self.assertEqual(b_value['size'], b.values[0].size)
        self.assertEqual(b_value['precision_horz'],
                         b.values[0].precision_horz)
        self.assertEqual(b_value['precision_vert'],
                         b.values[0].precision_vert)
        self.assertEqual(b_data, b.data)

        target = SimpleProvider()
        # No changes with self
        self.assertFalse(a.changes(a, target))
        # Diff in lat_direction causes change
        other = LocRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].lat_direction = 'N'
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in altitude causes change
        other.values[0].altitude = a.values[0].altitude
        other.values[0].altitude = -10
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)

        # __repr__ doesn't blow up
        a.__repr__()

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
        self.assertEqual('a', a.name)
        self.assertEqual('a.unit.tests.', a.fqdn)
        self.assertEqual(30, a.ttl)
        self.assertEqual(a_values[0]['preference'], a.values[0].preference)
        self.assertEqual(a_values[0]['exchange'], a.values[0].exchange)
        self.assertEqual(a_values[1]['priority'], a.values[1].preference)
        self.assertEqual(a_values[1]['value'], a.values[1].exchange)
        a_data['values'][1] = {
            'preference': 20,
            'exchange': 'smtp2.',
        }
        self.assertEqual(a_data, a.data)

        b_value = {
            'preference': 0,
            'exchange': 'smtp3.',
        }
        b_data = {'ttl': 30, 'value': b_value}
        b = MxRecord(self.zone, 'b', b_data)
        self.assertEqual(b_value['preference'], b.values[0].preference)
        self.assertEqual(b_value['exchange'], b.values[0].exchange)
        self.assertEqual(b_data, b.data)

        a_upper_values = [{
            'preference': 10,
            'exchange': 'SMTP1.'
        }, {
            'priority': 20,
            'value': 'SMTP2.'
        }]
        a_upper_data = {'ttl': 30, 'values': a_upper_values}
        a_upper = MxRecord(self.zone, 'a', a_upper_data)
        self.assertEqual(a_upper.data, a.data)

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
        self.assertEqual('a', a.name)
        self.assertEqual('a.unit.tests.', a.fqdn)
        self.assertEqual(30, a.ttl)
        for i in (0, 1):
            for k in a_values[0].keys():
                self.assertEqual(a_values[i][k], getattr(a.values[i], k))
        self.assertEqual(a_data, a.data)

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
            self.assertEqual(b_value[k], getattr(b.values[0], k))
        self.assertEqual(b_data, b.data)

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
        self.assertTrue(b_naptr_value == b_naptr_value)
        self.assertFalse(b_naptr_value != b_naptr_value)
        self.assertTrue(b_naptr_value <= b_naptr_value)
        self.assertTrue(b_naptr_value >= b_naptr_value)
        # by order
        self.assertTrue(b_naptr_value > NaptrValue({
            'order': 10,
            'preference': 31,
            'flags': 'M',
            'service': 'N',
            'regexp': 'O',
            'replacement': 'x',
        }))
        self.assertTrue(b_naptr_value < NaptrValue({
            'order': 40,
            'preference': 31,
            'flags': 'M',
            'service': 'N',
            'regexp': 'O',
            'replacement': 'x',
        }))
        # by preference
        self.assertTrue(b_naptr_value > NaptrValue({
            'order': 30,
            'preference': 10,
            'flags': 'M',
            'service': 'N',
            'regexp': 'O',
            'replacement': 'x',
        }))
        self.assertTrue(b_naptr_value < NaptrValue({
            'order': 30,
            'preference': 40,
            'flags': 'M',
            'service': 'N',
            'regexp': 'O',
            'replacement': 'x',
        }))
        # by flags
        self.assertTrue(b_naptr_value > NaptrValue({
            'order': 30,
            'preference': 31,
            'flags': 'A',
            'service': 'N',
            'regexp': 'O',
            'replacement': 'x',
        }))
        self.assertTrue(b_naptr_value < NaptrValue({
            'order': 30,
            'preference': 31,
            'flags': 'Z',
            'service': 'N',
            'regexp': 'O',
            'replacement': 'x',
        }))
        # by service
        self.assertTrue(b_naptr_value > NaptrValue({
            'order': 30,
            'preference': 31,
            'flags': 'M',
            'service': 'A',
            'regexp': 'O',
            'replacement': 'x',
        }))
        self.assertTrue(b_naptr_value < NaptrValue({
            'order': 30,
            'preference': 31,
            'flags': 'M',
            'service': 'Z',
            'regexp': 'O',
            'replacement': 'x',
        }))
        # by regexp
        self.assertTrue(b_naptr_value > NaptrValue({
            'order': 30,
            'preference': 31,
            'flags': 'M',
            'service': 'N',
            'regexp': 'A',
            'replacement': 'x',
        }))
        self.assertTrue(b_naptr_value < NaptrValue({
            'order': 30,
            'preference': 31,
            'flags': 'M',
            'service': 'N',
            'regexp': 'Z',
            'replacement': 'x',
        }))
        # by replacement
        self.assertTrue(b_naptr_value > NaptrValue({
            'order': 30,
            'preference': 31,
            'flags': 'M',
            'service': 'N',
            'regexp': 'O',
            'replacement': 'a',
        }))
        self.assertTrue(b_naptr_value < NaptrValue({
            'order': 30,
            'preference': 31,
            'flags': 'M',
            'service': 'N',
            'regexp': 'O',
            'replacement': 'z',
        }))

        # __repr__ doesn't blow up
        a.__repr__()

        # Hash
        v = NaptrValue({
            'order': 30,
            'preference': 31,
            'flags': 'M',
            'service': 'N',
            'regexp': 'O',
            'replacement': 'z',
        })
        o = NaptrValue({
            'order': 30,
            'preference': 32,
            'flags': 'M',
            'service': 'N',
            'regexp': 'O',
            'replacement': 'z',
        })
        values = set()
        values.add(v)
        self.assertTrue(v in values)
        self.assertFalse(o in values)
        values.add(o)
        self.assertTrue(o in values)

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
        self.assertEqual('a', a.name)
        self.assertEqual('a.unit.tests.', a.fqdn)
        self.assertEqual(30, a.ttl)
        self.assertEqual(a_values[0]['algorithm'], a.values[0].algorithm)
        self.assertEqual(a_values[0]['fingerprint_type'],
                         a.values[0].fingerprint_type)
        self.assertEqual(a_values[0]['fingerprint'], a.values[0].fingerprint)
        self.assertEqual(a_data, a.data)

        b_value = {
            'algorithm': 30,
            'fingerprint_type': 31,
            'fingerprint': 'ghi789',
        }
        b_data = {'ttl': 30, 'value': b_value}
        b = SshfpRecord(self.zone, 'b', b_data)
        self.assertEqual(b_value['algorithm'], b.values[0].algorithm)
        self.assertEqual(b_value['fingerprint_type'],
                         b.values[0].fingerprint_type)
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
        self.assertEqual('_a._tcp', a.name)
        self.assertEqual('_a._tcp.unit.tests.', a.fqdn)
        self.assertEqual(30, a.ttl)
        self.assertEqual(a_values[0]['priority'], a.values[0].priority)
        self.assertEqual(a_values[0]['weight'], a.values[0].weight)
        self.assertEqual(a_values[0]['port'], a.values[0].port)
        self.assertEqual(a_values[0]['target'], a.values[0].target)
        self.assertEqual(a_data, a.data)

        b_value = {
            'priority': 30,
            'weight': 31,
            'port': 32,
            'target': 'server3',
        }
        b_data = {'ttl': 30, 'value': b_value}
        b = SrvRecord(self.zone, '_b._tcp', b_data)
        self.assertEqual(b_value['priority'], b.values[0].priority)
        self.assertEqual(b_value['weight'], b.values[0].weight)
        self.assertEqual(b_value['port'], b.values[0].port)
        self.assertEqual(b_value['target'], b.values[0].target)
        self.assertEqual(b_data, b.data)

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

    def test_urlfwd(self):
        a_values = [{
            'path': '/',
            'target': 'http://foo',
            'code': 301,
            'masking': 2,
            'query': 0,
        }, {
            'path': '/target',
            'target': 'http://target',
            'code': 302,
            'masking': 2,
            'query': 0,
        }]
        a_data = {'ttl': 30, 'values': a_values}
        a = UrlfwdRecord(self.zone, 'a', a_data)
        self.assertEqual('a', a.name)
        self.assertEqual('a.unit.tests.', a.fqdn)
        self.assertEqual(30, a.ttl)
        self.assertEqual(a_values[0]['path'], a.values[0].path)
        self.assertEqual(a_values[0]['target'], a.values[0].target)
        self.assertEqual(a_values[0]['code'], a.values[0].code)
        self.assertEqual(a_values[0]['masking'], a.values[0].masking)
        self.assertEqual(a_values[0]['query'], a.values[0].query)
        self.assertEqual(a_values[1]['path'], a.values[1].path)
        self.assertEqual(a_values[1]['target'], a.values[1].target)
        self.assertEqual(a_values[1]['code'], a.values[1].code)
        self.assertEqual(a_values[1]['masking'], a.values[1].masking)
        self.assertEqual(a_values[1]['query'], a.values[1].query)
        self.assertEqual(a_data, a.data)

        b_value = {
            'path': '/',
            'target': 'http://location',
            'code': 301,
            'masking': 2,
            'query': 0,
        }
        b_data = {'ttl': 30, 'value': b_value}
        b = UrlfwdRecord(self.zone, 'b', b_data)
        self.assertEqual(b_value['path'], b.values[0].path)
        self.assertEqual(b_value['target'], b.values[0].target)
        self.assertEqual(b_value['code'], b.values[0].code)
        self.assertEqual(b_value['masking'], b.values[0].masking)
        self.assertEqual(b_value['query'], b.values[0].query)
        self.assertEqual(b_data, b.data)

        target = SimpleProvider()
        # No changes with self
        self.assertFalse(a.changes(a, target))
        # Diff in path causes change
        other = UrlfwdRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].path = '/change'
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in target causes change
        other = UrlfwdRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].target = 'http://target'
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in code causes change
        other = UrlfwdRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].code = 302
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in masking causes change
        other = UrlfwdRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].masking = 0
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)
        # Diff in query causes change
        other = UrlfwdRecord(self.zone, 'a', {'ttl': 30, 'values': a_values})
        other.values[0].query = 1
        change = a.changes(other, target)
        self.assertEqual(change.existing, a)
        self.assertEqual(change.new, other)

        # hash
        v = UrlfwdValue({
            'path': '/',
            'target': 'http://place',
            'code': 301,
            'masking': 2,
            'query': 0,
        })
        o = UrlfwdValue({
            'path': '/location',
            'target': 'http://redirect',
            'code': 302,
            'masking': 2,
            'query': 0,
        })
        values = set()
        values.add(v)
        self.assertTrue(v in values)
        self.assertFalse(o in values)
        values.add(o)
        self.assertTrue(o in values)

        # __repr__ doesn't blow up
        a.__repr__()

    def test_record_new(self):
        txt = Record.new(self.zone, 'txt', {
            'ttl': 44,
            'type': 'TXT',
            'value': 'some text',
        })
        self.assertIsInstance(txt, TxtRecord)
        self.assertEqual('TXT', txt._type)
        self.assertEqual(['some text'], txt.values)

        # Missing type
        with self.assertRaises(Exception) as ctx:
            Record.new(self.zone, 'unknown', {})
        self.assertTrue('missing type' in str(ctx.exception))

        # Unknown type
        with self.assertRaises(Exception) as ctx:
            Record.new(self.zone, 'unknown', {
                'type': 'XXX',
            })
        self.assertTrue('Unknown record type' in str(ctx.exception))

    def test_record_copy(self):
        a = Record.new(self.zone, 'a', {
            'ttl': 44,
            'type': 'A',
            'value': '1.2.3.4',
        })

        # Identical copy.
        b = a.copy()
        self.assertIsInstance(b, ARecord)
        self.assertEqual('unit.tests.', b.zone.name)
        self.assertEqual('a', b.name)
        self.assertEqual('A', b._type)
        self.assertEqual(['1.2.3.4'], b.values)

        # Copy with another zone object.
        c_zone = Zone('other.tests.', [])
        c = a.copy(c_zone)
        self.assertIsInstance(c, ARecord)
        self.assertEqual('other.tests.', c.zone.name)
        self.assertEqual('a', c.name)
        self.assertEqual('A', c._type)
        self.assertEqual(['1.2.3.4'], c.values)

        # Record with no record type specified in data.
        d_data = {
            'ttl': 600,
            'values': ['just a test']
        }
        d = TxtRecord(self.zone, 'txt', d_data)
        d.copy()
        self.assertEqual('TXT', d._type)

    def test_dynamic_record_copy(self):
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': '3.3.3.3',
                        }],
                    },
                },
                'rules': [{
                    'pool': 'one',
                }],
            },
            'octodns': {
                'healthcheck': {
                    'protocol': 'TCP',
                    'port': 80,
                },
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        record1 = Record.new(self.zone, 'a', a_data)
        record2 = record1.copy()
        self.assertEqual(record1._octodns, record2._octodns)

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
        self.assertEqual(new.values, create.record.values)
        update = Update(existing, new)
        self.assertEqual(new.values, update.record.values)
        delete = Delete(existing)
        self.assertEqual(existing.values, delete.record.values)

    def test_geo_value(self):
        code = 'NA-US-CA'
        values = ['1.2.3.4']
        geo = GeoValue(code, values)
        self.assertEqual(code, geo.code)
        self.assertEqual('NA', geo.continent_code)
        self.assertEqual('US', geo.country_code)
        self.assertEqual('CA', geo.subdivision_code)
        self.assertEqual(values, geo.values)
        self.assertEqual(['NA-US', 'NA'], list(geo.parents))

        a = GeoValue('NA-US-CA', values)
        b = GeoValue('AP-JP', values)
        c = GeoValue('NA-US-CA', ['2.3.4.5'])

        self.assertEqual(a, a)
        self.assertEqual(b, b)
        self.assertEqual(c, c)

        self.assertNotEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertNotEqual(b, a)
        self.assertNotEqual(b, c)
        self.assertNotEqual(c, a)
        self.assertNotEqual(c, b)

        self.assertTrue(a > b)
        self.assertTrue(a < c)
        self.assertTrue(b < a)
        self.assertTrue(b < c)
        self.assertTrue(c > a)
        self.assertTrue(c > b)

        self.assertTrue(a >= a)
        self.assertTrue(a >= b)
        self.assertTrue(a <= c)
        self.assertTrue(b <= a)
        self.assertTrue(b <= b)
        self.assertTrue(b <= c)
        self.assertTrue(c > a)
        self.assertTrue(c > b)
        self.assertTrue(c >= b)

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
        self.assertEqual('/_ready', new.healthcheck_path)
        self.assertEqual('bleep.bloop', new.healthcheck_host())
        self.assertEqual('HTTP', new.healthcheck_protocol)
        self.assertEqual(8080, new.healthcheck_port)

        # empty host value in healthcheck
        new = Record.new(self.zone, 'a', {
            'ttl': 44,
            'type': 'A',
            'value': '1.2.3.4',
            'octodns': {
                'healthcheck': {
                    'path': '/_ready',
                    'host': None,
                    'protocol': 'HTTP',
                    'port': 8080,
                }
            }
        })
        self.assertEqual('1.2.3.4', new.healthcheck_host(value="1.2.3.4"))

        new = Record.new(self.zone, 'a', {
            'ttl': 44,
            'type': 'A',
            'value': '1.2.3.4',
        })
        self.assertEqual('/_dns', new.healthcheck_path)
        self.assertEqual('a.unit.tests', new.healthcheck_host())
        self.assertEqual('HTTPS', new.healthcheck_protocol)
        self.assertEqual(443, new.healthcheck_port)

    def test_healthcheck_tcp(self):
        new = Record.new(self.zone, 'a', {
            'ttl': 44,
            'type': 'A',
            'value': '1.2.3.4',
            'octodns': {
                'healthcheck': {
                    'path': '/ignored',
                    'host': 'completely.ignored',
                    'protocol': 'TCP',
                    'port': 8080,
                }
            }
        })
        self.assertIsNone(new.healthcheck_path)
        self.assertIsNone(new.healthcheck_host())
        self.assertEqual('TCP', new.healthcheck_protocol)
        self.assertEqual(8080, new.healthcheck_port)

        new = Record.new(self.zone, 'a', {
            'ttl': 44,
            'type': 'A',
            'value': '1.2.3.4',
            'octodns': {
                'healthcheck': {
                    'protocol': 'TCP',
                }
            }
        })
        self.assertIsNone(new.healthcheck_path)
        self.assertIsNone(new.healthcheck_host())
        self.assertEqual('TCP', new.healthcheck_protocol)
        self.assertEqual(443, new.healthcheck_port)

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

    def test_ordering_functions(self):
        a = Record.new(self.zone, 'a', {
            'ttl': 44,
            'type': 'A',
            'value': '1.2.3.4',
        })
        b = Record.new(self.zone, 'b', {
            'ttl': 44,
            'type': 'A',
            'value': '1.2.3.4',
        })
        c = Record.new(self.zone, 'c', {
            'ttl': 44,
            'type': 'A',
            'value': '1.2.3.4',
        })
        aaaa = Record.new(self.zone, 'a', {
            'ttl': 44,
            'type': 'AAAA',
            'value': '2601:644:500:e210:62f8:1dff:feb8:947a',
        })

        self.assertEqual(a, a)
        self.assertEqual(b, b)
        self.assertEqual(c, c)
        self.assertEqual(aaaa, aaaa)

        self.assertNotEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertNotEqual(a, aaaa)
        self.assertNotEqual(b, a)
        self.assertNotEqual(b, c)
        self.assertNotEqual(b, aaaa)
        self.assertNotEqual(c, a)
        self.assertNotEqual(c, b)
        self.assertNotEqual(c, aaaa)
        self.assertNotEqual(aaaa, a)
        self.assertNotEqual(aaaa, b)
        self.assertNotEqual(aaaa, c)

        self.assertTrue(a < b)
        self.assertTrue(a < c)
        self.assertTrue(a < aaaa)
        self.assertTrue(b > a)
        self.assertTrue(b < c)
        self.assertTrue(b > aaaa)
        self.assertTrue(c > a)
        self.assertTrue(c > b)
        self.assertTrue(c > aaaa)
        self.assertTrue(aaaa > a)
        self.assertTrue(aaaa < b)
        self.assertTrue(aaaa < c)

        self.assertTrue(a <= a)
        self.assertTrue(a <= b)
        self.assertTrue(a <= c)
        self.assertTrue(a <= aaaa)
        self.assertTrue(b >= a)
        self.assertTrue(b >= b)
        self.assertTrue(b <= c)
        self.assertTrue(b >= aaaa)
        self.assertTrue(c >= a)
        self.assertTrue(c >= b)
        self.assertTrue(c >= c)
        self.assertTrue(c >= aaaa)
        self.assertTrue(aaaa >= a)
        self.assertTrue(aaaa <= b)
        self.assertTrue(aaaa <= c)
        self.assertTrue(aaaa <= aaaa)

    def test_caa_value(self):
        a = CaaValue({'flags': 0, 'tag': 'a', 'value': 'v'})
        b = CaaValue({'flags': 1, 'tag': 'a', 'value': 'v'})
        c = CaaValue({'flags': 0, 'tag': 'c', 'value': 'v'})
        d = CaaValue({'flags': 0, 'tag': 'a', 'value': 'z'})

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

        self.assertTrue(a < b)
        self.assertTrue(a < c)
        self.assertTrue(a < d)

        self.assertTrue(b > a)
        self.assertTrue(b > c)
        self.assertTrue(b > d)

        self.assertTrue(c > a)
        self.assertTrue(c < b)
        self.assertTrue(c > d)

        self.assertTrue(d > a)
        self.assertTrue(d < b)
        self.assertTrue(d < c)

        self.assertTrue(a <= b)
        self.assertTrue(a <= c)
        self.assertTrue(a <= d)
        self.assertTrue(a <= a)
        self.assertTrue(a >= a)

        self.assertTrue(b >= a)
        self.assertTrue(b >= c)
        self.assertTrue(b >= d)
        self.assertTrue(b >= b)
        self.assertTrue(b <= b)

        self.assertTrue(c >= a)
        self.assertTrue(c <= b)
        self.assertTrue(c >= d)
        self.assertTrue(c >= c)
        self.assertTrue(c <= c)

        self.assertTrue(d >= a)
        self.assertTrue(d <= b)
        self.assertTrue(d <= c)
        self.assertTrue(d >= d)
        self.assertTrue(d <= d)

    def test_loc_value(self):
        a = LocValue({
            'lat_degrees': 31,
            'lat_minutes': 58,
            'lat_seconds': 52.1,
            'lat_direction': 'S',
            'long_degrees': 115,
            'long_minutes': 49,
            'long_seconds': 11.7,
            'long_direction': 'E',
            'altitude': 20,
            'size': 10,
            'precision_horz': 10,
            'precision_vert': 2,
        })
        b = LocValue({
            'lat_degrees': 32,
            'lat_minutes': 7,
            'lat_seconds': 19,
            'lat_direction': 'S',
            'long_degrees': 116,
            'long_minutes': 2,
            'long_seconds': 25,
            'long_direction': 'E',
            'altitude': 10,
            'size': 1,
            'precision_horz': 10000,
            'precision_vert': 10,
        })
        c = LocValue({
            'lat_degrees': 53,
            'lat_minutes': 14,
            'lat_seconds': 10,
            'lat_direction': 'N',
            'long_degrees': 2,
            'long_minutes': 18,
            'long_seconds': 26,
            'long_direction': 'W',
            'altitude': 10,
            'size': 1,
            'precision_horz': 1000,
            'precision_vert': 10,
        })

        self.assertEqual(a, a)
        self.assertEqual(b, b)
        self.assertEqual(c, c)

        self.assertNotEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertNotEqual(b, a)
        self.assertNotEqual(b, c)
        self.assertNotEqual(c, a)
        self.assertNotEqual(c, b)

        self.assertTrue(a < b)
        self.assertTrue(a < c)

        self.assertTrue(b > a)
        self.assertTrue(b < c)

        self.assertTrue(c > a)
        self.assertTrue(c > b)

        self.assertTrue(a <= b)
        self.assertTrue(a <= c)
        self.assertTrue(a <= a)
        self.assertTrue(a >= a)

        self.assertTrue(b >= a)
        self.assertTrue(b <= c)
        self.assertTrue(b >= b)
        self.assertTrue(b <= b)

        self.assertTrue(c >= a)
        self.assertTrue(c >= b)
        self.assertTrue(c >= c)
        self.assertTrue(c <= c)

        # Hash
        values = set()
        values.add(a)
        self.assertTrue(a in values)
        self.assertFalse(b in values)
        values.add(b)
        self.assertTrue(b in values)

    def test_mx_value(self):
        a = MxValue({'preference': 0, 'priority': 'a', 'exchange': 'v',
                     'value': '1'})
        b = MxValue({'preference': 10, 'priority': 'a', 'exchange': 'v',
                     'value': '2'})
        c = MxValue({'preference': 0, 'priority': 'b', 'exchange': 'z',
                     'value': '3'})

        self.assertEqual(a, a)
        self.assertEqual(b, b)
        self.assertEqual(c, c)

        self.assertNotEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertNotEqual(b, a)
        self.assertNotEqual(b, c)
        self.assertNotEqual(c, a)
        self.assertNotEqual(c, b)

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

        self.assertEqual(a.__hash__(), a.__hash__())
        self.assertNotEqual(a.__hash__(), b.__hash__())

    def test_sshfp_value(self):
        a = SshfpValue({'algorithm': 0, 'fingerprint_type': 0,
                        'fingerprint': 'abcd'})
        b = SshfpValue({'algorithm': 1, 'fingerprint_type': 0,
                        'fingerprint': 'abcd'})
        c = SshfpValue({'algorithm': 0, 'fingerprint_type': 1,
                        'fingerprint': 'abcd'})
        d = SshfpValue({'algorithm': 0, 'fingerprint_type': 0,
                        'fingerprint': 'bcde'})

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

    def test_srv_value(self):
        a = SrvValue({'priority': 0, 'weight': 0, 'port': 0, 'target': 'foo.'})
        b = SrvValue({'priority': 1, 'weight': 0, 'port': 0, 'target': 'foo.'})
        c = SrvValue({'priority': 0, 'weight': 2, 'port': 0, 'target': 'foo.'})
        d = SrvValue({'priority': 0, 'weight': 0, 'port': 3, 'target': 'foo.'})
        e = SrvValue({'priority': 0, 'weight': 0, 'port': 0, 'target': 'mmm.'})

        self.assertEqual(a, a)
        self.assertEqual(b, b)
        self.assertEqual(c, c)
        self.assertEqual(d, d)
        self.assertEqual(e, e)

        self.assertNotEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertNotEqual(a, d)
        self.assertNotEqual(a, e)
        self.assertNotEqual(b, a)
        self.assertNotEqual(b, c)
        self.assertNotEqual(b, d)
        self.assertNotEqual(b, e)
        self.assertNotEqual(c, a)
        self.assertNotEqual(c, b)
        self.assertNotEqual(c, d)
        self.assertNotEqual(c, e)
        self.assertNotEqual(d, a)
        self.assertNotEqual(d, b)
        self.assertNotEqual(d, c)
        self.assertNotEqual(d, e)
        self.assertNotEqual(e, a)
        self.assertNotEqual(e, b)
        self.assertNotEqual(e, c)
        self.assertNotEqual(e, d)

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


class TestRecordValidation(TestCase):
    zone = Zone('unit.tests.', [])

    def test_base(self):
        # name = '@'
        with self.assertRaises(ValidationError) as ctx:
            name = '@'
            Record.new(self.zone, name, {
                'ttl': 300,
                'type': 'A',
                'value': '1.2.3.4',
            })
        reason = ctx.exception.reasons[0]
        self.assertTrue(reason.startswith('invalid name "@", use "" instead'))

        # fqdn length, DNS defins max as 253
        with self.assertRaises(ValidationError) as ctx:
            # The . will put this over the edge
            name = 'x' * (253 - len(self.zone.name))
            Record.new(self.zone, name, {
                'ttl': 300,
                'type': 'A',
                'value': '1.2.3.4',
            })
        reason = ctx.exception.reasons[0]
        self.assertTrue(reason.startswith('invalid fqdn, "xxxx'))
        self.assertTrue(reason.endswith('.unit.tests." is too long at 254'
                                        ' chars, max is 253'))

        # label length, DNS defines max as 63
        with self.assertRaises(ValidationError) as ctx:
            # The . will put this over the edge
            name = 'x' * 64
            Record.new(self.zone, name, {
                'ttl': 300,
                'type': 'A',
                'value': '1.2.3.4',
            })
        reason = ctx.exception.reasons[0]
        self.assertTrue(reason.startswith('invalid label, "xxxx'))
        self.assertTrue(reason.endswith('xxx" is too long at 64'
                                        ' chars, max is 63'))

        with self.assertRaises(ValidationError) as ctx:
            name = 'foo.' + 'x' * 64 + '.bar'
            Record.new(self.zone, name, {
                'ttl': 300,
                'type': 'A',
                'value': '1.2.3.4',
            })
        reason = ctx.exception.reasons[0]
        self.assertTrue(reason.startswith('invalid label, "xxxx'))
        self.assertTrue(reason.endswith('xxx" is too long at 64'
                                        ' chars, max is 63'))

        # should not raise with dots
        name = 'xxxxxxxx.' * 10
        Record.new(self.zone, name, {
            'ttl': 300,
            'type': 'A',
            'value': '1.2.3.4',
        })

        # no ttl
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'A',
                'value': '1.2.3.4',
            })
        self.assertEqual(['missing ttl'], ctx.exception.reasons)

        # invalid ttl
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'A',
                'ttl': -1,
                'value': '1.2.3.4',
            })
        self.assertEqual('www.unit.tests.', ctx.exception.fqdn)
        self.assertEqual(['invalid ttl'], ctx.exception.reasons)

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
        self.assertEqual(('value',), ctx.exception.args)

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
        self.assertEqual(['missing value(s)'], ctx.exception.reasons)

        # missing value(s), empty values
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'A',
                'ttl': 600,
                'values': []
            })
        self.assertEqual(['missing value(s)'], ctx.exception.reasons)

        # missing value(s), None values
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'A',
                'ttl': 600,
                'values': None
            })
        self.assertEqual(['missing value(s)'], ctx.exception.reasons)

        # missing value(s) and empty value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'A',
                'ttl': 600,
                'values': [None, '']
            })
        self.assertEqual(['missing value(s)',
                          'empty value'], ctx.exception.reasons)

        # missing value(s), None value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'A',
                'ttl': 600,
                'value': None
            })
        self.assertEqual(['missing value(s)'], ctx.exception.reasons)

        # empty value, empty string value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'A',
                'ttl': 600,
                'value': ''
            })
        self.assertEqual(['empty value'], ctx.exception.reasons)

        # missing value(s) & ttl
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'A',
            })
        self.assertEqual(['missing ttl', 'missing value(s)'],
                         ctx.exception.reasons)

        # invalid ipv4 address
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'A',
                'ttl': 600,
                'value': 'hello'
            })
        self.assertEqual(['invalid IPv4 address "hello"'],
                         ctx.exception.reasons)

        # invalid ipv4 addresses
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'A',
                'ttl': 600,
                'values': ['hello', 'goodbye']
            })
        self.assertEqual([
            'invalid IPv4 address "hello"',
            'invalid IPv4 address "goodbye"'
        ], ctx.exception.reasons)

        # invalid & valid ipv4 addresses, no ttl
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'A',
                'values': ['1.2.3.4', 'hello', '5.6.7.8']
            })
        self.assertEqual([
            'missing ttl',
            'invalid IPv4 address "hello"',
        ], ctx.exception.reasons)

    def test_AAAA_validation(self):
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
            ]
        })
        Record.new(self.zone, '', {
            'type': 'AAAA',
            'ttl': 600,
            'values': [
                '2601:644:500:e210:62f8:1dff:feb8:947a',
                '2601:642:500:e210:62f8:1dff:feb8:947a',
            ]
        })

        # missing value(s), no value or value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'AAAA',
                'ttl': 600,
            })
        self.assertEqual(['missing value(s)'], ctx.exception.reasons)

        # missing value(s), empty values
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'AAAA',
                'ttl': 600,
                'values': []
            })
        self.assertEqual(['missing value(s)'], ctx.exception.reasons)

        # missing value(s), None values
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'AAAA',
                'ttl': 600,
                'values': None
            })
        self.assertEqual(['missing value(s)'], ctx.exception.reasons)

        # missing value(s) and empty value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'AAAA',
                'ttl': 600,
                'values': [None, '']
            })
        self.assertEqual(['missing value(s)',
                          'empty value'], ctx.exception.reasons)

        # missing value(s), None value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'AAAA',
                'ttl': 600,
                'value': None
            })
        self.assertEqual(['missing value(s)'], ctx.exception.reasons)

        # empty value, empty string value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'AAAA',
                'ttl': 600,
                'value': ''
            })
        self.assertEqual(['empty value'], ctx.exception.reasons)

        # missing value(s) & ttl
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'AAAA',
            })
        self.assertEqual(['missing ttl', 'missing value(s)'],
                         ctx.exception.reasons)

        # invalid IPv6 address
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'AAAA',
                'ttl': 600,
                'value': 'hello'
            })
        self.assertEqual(['invalid IPv6 address "hello"'],
                         ctx.exception.reasons)

        # invalid IPv6 addresses
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'AAAA',
                'ttl': 600,
                'values': ['hello', 'goodbye']
            })
        self.assertEqual([
            'invalid IPv6 address "hello"',
            'invalid IPv6 address "goodbye"'
        ], ctx.exception.reasons)

        # invalid & valid IPv6 addresses, no ttl
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'AAAA',
                'values': [
                    '2601:644:500:e210:62f8:1dff:feb8:947a',
                    'hello',
                    '2601:642:500:e210:62f8:1dff:feb8:947a'
                ]
            })
        self.assertEqual([
            'missing ttl',
            'invalid IPv6 address "hello"',
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
        self.assertEqual(['invalid IPv4 address "hello"'],
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
        self.assertEqual(['invalid geo "XYZ"'], ctx.exception.reasons)

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
        self.assertEqual([
            'invalid IPv4 address "hello"',
            'invalid IPv4 address "goodbye"'
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
        self.assertEqual(['invalid healthcheck protocol'],
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
        self.assertEqual(['invalid IPv6 address "hello"'],
                         ctx.exception.reasons)
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'AAAA',
                'ttl': 600,
                'values': [
                    '1.2.3.4',
                    '2.3.4.5',
                ],
            })
        self.assertEqual([
            'invalid IPv6 address "1.2.3.4"',
            'invalid IPv6 address "2.3.4.5"',
        ], ctx.exception.reasons)

        # invalid ip addresses
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'AAAA',
                'ttl': 600,
                'values': ['hello', 'goodbye']
            })
        self.assertEqual([
            'invalid IPv6 address "hello"',
            'invalid IPv6 address "goodbye"'
        ], ctx.exception.reasons)

    def test_ALIAS_and_value_mixin(self):
        # doesn't blow up
        Record.new(self.zone, '', {
            'type': 'ALIAS',
            'ttl': 600,
            'value': 'foo.bar.com.',
        })

        # root only
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'nope', {
                'type': 'ALIAS',
                'ttl': 600,
                'value': 'foo.bar.com.',
            })
        self.assertEqual(['non-root ALIAS not allowed'],
                         ctx.exception.reasons)

        # missing value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'ALIAS',
                'ttl': 600,
            })
        self.assertEqual(['missing value'], ctx.exception.reasons)

        # missing value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'ALIAS',
                'ttl': 600,
                'value': None
            })
        self.assertEqual(['missing value'], ctx.exception.reasons)

        # empty value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'ALIAS',
                'ttl': 600,
                'value': ''
            })
        self.assertEqual(['empty value'], ctx.exception.reasons)

        # not a valid FQDN
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'ALIAS',
                'ttl': 600,
                'value': '__.',
            })
        self.assertEqual(['ALIAS value "__." is not a valid FQDN'],
                         ctx.exception.reasons)

        # missing trailing .
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'ALIAS',
                'ttl': 600,
                'value': 'foo.bar.com',
            })
        self.assertEqual(['ALIAS value "foo.bar.com" missing trailing .'],
                         ctx.exception.reasons)

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
        self.assertEqual(['invalid flags "-42"'], ctx.exception.reasons)
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
        self.assertEqual(['invalid flags "442"'], ctx.exception.reasons)
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
        self.assertEqual(['invalid flags "nope"'], ctx.exception.reasons)

        # missing tag
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'CAA',
                'ttl': 600,
                'value': {
                    'value': 'http://foo.bar.com/',
                }
            })
        self.assertEqual(['missing tag'], ctx.exception.reasons)

        # missing value
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'CAA',
                'ttl': 600,
                'value': {
                    'tag': 'iodef',
                }
            })
        self.assertEqual(['missing value'], ctx.exception.reasons)

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
        self.assertEqual(['root CNAME not allowed'], ctx.exception.reasons)

        # not a valid FQDN
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'CNAME',
                'ttl': 600,
                'value': '___.',
            })
        self.assertEqual(['CNAME value "___." is not a valid FQDN'],
                         ctx.exception.reasons)

        # missing trailing .
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'CNAME',
                'ttl': 600,
                'value': 'foo.bar.com',
            })
        self.assertEqual(['CNAME value "foo.bar.com" missing trailing .'],
                         ctx.exception.reasons)

        # doesn't allow urls
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'CNAME',
                'ttl': 600,
                'value': 'https://google.com',
            })
        self.assertEqual(['CNAME value "https://google.com" is not a valid '
                          'FQDN'], ctx.exception.reasons)

        # doesn't allow urls with paths
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'CNAME',
                'ttl': 600,
                'value': 'https://google.com/a/b/c',
            })
        self.assertEqual(['CNAME value "https://google.com/a/b/c" is not a '
                          'valid FQDN'], ctx.exception.reasons)

        # doesn't allow paths
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'CNAME',
                'ttl': 600,
                'value': 'google.com/some/path',
            })
        self.assertEqual(['CNAME value "google.com/some/path" is not a valid '
                          'FQDN'], ctx.exception.reasons)

    def test_DNAME(self):
        # A valid DNAME record.
        Record.new(self.zone, 'sub', {
            'type': 'DNAME',
            'ttl': 600,
            'value': 'foo.bar.com.',
        })

        # A DNAME record can be present at the zone APEX.
        Record.new(self.zone, '', {
            'type': 'DNAME',
            'ttl': 600,
            'value': 'foo.bar.com.',
        })

        # not a valid FQDN
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'DNAME',
                'ttl': 600,
                'value': '.',
            })
        self.assertEqual(['DNAME value "." is not a valid FQDN'],
                         ctx.exception.reasons)

        # missing trailing .
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'www', {
                'type': 'DNAME',
                'ttl': 600,
                'value': 'foo.bar.com',
            })
        self.assertEqual(['DNAME value "foo.bar.com" missing trailing .'],
                         ctx.exception.reasons)

    def test_LOC(self):
        # doesn't blow up
        Record.new(self.zone, '', {
            'type': 'LOC',
            'ttl': 600,
            'value': {
                'lat_degrees': 31,
                'lat_minutes': 58,
                'lat_seconds': 52.1,
                'lat_direction': 'S',
                'long_degrees': 115,
                'long_minutes': 49,
                'long_seconds': 11.7,
                'long_direction': 'E',
                'altitude': 20,
                'size': 10,
                'precision_horz': 10,
                'precision_vert': 2,
            }
        })

        # missing int key
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'LOC',
                'ttl': 600,
                'value': {
                    'lat_minutes': 58,
                    'lat_seconds': 52.1,
                    'lat_direction': 'S',
                    'long_degrees': 115,
                    'long_minutes': 49,
                    'long_seconds': 11.7,
                    'long_direction': 'E',
                    'altitude': 20,
                    'size': 10,
                    'precision_horz': 10,
                    'precision_vert': 2,
                }
            })

        self.assertEqual(['missing lat_degrees'], ctx.exception.reasons)

        # missing float key
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'LOC',
                'ttl': 600,
                'value': {
                    'lat_degrees': 31,
                    'lat_minutes': 58,
                    'lat_direction': 'S',
                    'long_degrees': 115,
                    'long_minutes': 49,
                    'long_seconds': 11.7,
                    'long_direction': 'E',
                    'altitude': 20,
                    'size': 10,
                    'precision_horz': 10,
                    'precision_vert': 2,
                }
            })

        self.assertEqual(['missing lat_seconds'], ctx.exception.reasons)

        # missing text key
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'LOC',
                'ttl': 600,
                'value': {
                    'lat_degrees': 31,
                    'lat_minutes': 58,
                    'lat_seconds': 52.1,
                    'long_degrees': 115,
                    'long_minutes': 49,
                    'long_seconds': 11.7,
                    'long_direction': 'E',
                    'altitude': 20,
                    'size': 10,
                    'precision_horz': 10,
                    'precision_vert': 2,
                }
            })

        self.assertEqual(['missing lat_direction'], ctx.exception.reasons)

        # invalid direction
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'LOC',
                'ttl': 600,
                'value': {
                    'lat_degrees': 31,
                    'lat_minutes': 58,
                    'lat_seconds': 52.1,
                    'lat_direction': 'U',
                    'long_degrees': 115,
                    'long_minutes': 49,
                    'long_seconds': 11.7,
                    'long_direction': 'E',
                    'altitude': 20,
                    'size': 10,
                    'precision_horz': 10,
                    'precision_vert': 2,
                }
            })

        self.assertEqual(['invalid direction for lat_direction "U"'],
                         ctx.exception.reasons)

        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'LOC',
                'ttl': 600,
                'value': {
                    'lat_degrees': 31,
                    'lat_minutes': 58,
                    'lat_seconds': 52.1,
                    'lat_direction': 'S',
                    'long_degrees': 115,
                    'long_minutes': 49,
                    'long_seconds': 11.7,
                    'long_direction': 'N',
                    'altitude': 20,
                    'size': 10,
                    'precision_horz': 10,
                    'precision_vert': 2,
                }
            })

        self.assertEqual(['invalid direction for long_direction "N"'],
                         ctx.exception.reasons)

        # invalid degrees
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'LOC',
                'ttl': 600,
                'value': {
                    'lat_degrees': 360,
                    'lat_minutes': 58,
                    'lat_seconds': 52.1,
                    'lat_direction': 'S',
                    'long_degrees': 115,
                    'long_minutes': 49,
                    'long_seconds': 11.7,
                    'long_direction': 'E',
                    'altitude': 20,
                    'size': 10,
                    'precision_horz': 10,
                    'precision_vert': 2,
                }
            })

        self.assertEqual(['invalid value for lat_degrees "360"'],
                         ctx.exception.reasons)

        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'LOC',
                'ttl': 600,
                'value': {
                    'lat_degrees': 'nope',
                    'lat_minutes': 58,
                    'lat_seconds': 52.1,
                    'lat_direction': 'S',
                    'long_degrees': 115,
                    'long_minutes': 49,
                    'long_seconds': 11.7,
                    'long_direction': 'E',
                    'altitude': 20,
                    'size': 10,
                    'precision_horz': 10,
                    'precision_vert': 2,
                }
            })

        self.assertEqual(['invalid lat_degrees "nope"'],
                         ctx.exception.reasons)

        # invalid minutes
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'LOC',
                'ttl': 600,
                'value': {
                    'lat_degrees': 31,
                    'lat_minutes': 60,
                    'lat_seconds': 52.1,
                    'lat_direction': 'S',
                    'long_degrees': 115,
                    'long_minutes': 49,
                    'long_seconds': 11.7,
                    'long_direction': 'E',
                    'altitude': 20,
                    'size': 10,
                    'precision_horz': 10,
                    'precision_vert': 2,
                }
            })

        self.assertEqual(['invalid value for lat_minutes "60"'],
                         ctx.exception.reasons)

        # invalid seconds
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'LOC',
                'ttl': 600,
                'value': {
                    'lat_degrees': 31,
                    'lat_minutes': 58,
                    'lat_seconds': 60,
                    'lat_direction': 'S',
                    'long_degrees': 115,
                    'long_minutes': 49,
                    'long_seconds': 11.7,
                    'long_direction': 'E',
                    'altitude': 20,
                    'size': 10,
                    'precision_horz': 10,
                    'precision_vert': 2,
                }
            })

        self.assertEqual(['invalid value for lat_seconds "60"'],
                         ctx.exception.reasons)

        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'LOC',
                'ttl': 600,
                'value': {
                    'lat_degrees': 31,
                    'lat_minutes': 58,
                    'lat_seconds': 'nope',
                    'lat_direction': 'S',
                    'long_degrees': 115,
                    'long_minutes': 49,
                    'long_seconds': 11.7,
                    'long_direction': 'E',
                    'altitude': 20,
                    'size': 10,
                    'precision_horz': 10,
                    'precision_vert': 2,
                }
            })

        self.assertEqual(['invalid lat_seconds "nope"'],
                         ctx.exception.reasons)

        # invalid altitude
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'LOC',
                'ttl': 600,
                'value': {
                    'lat_degrees': 31,
                    'lat_minutes': 58,
                    'lat_seconds': 52.1,
                    'lat_direction': 'S',
                    'long_degrees': 115,
                    'long_minutes': 49,
                    'long_seconds': 11.7,
                    'long_direction': 'E',
                    'altitude': -666666,
                    'size': 10,
                    'precision_horz': 10,
                    'precision_vert': 2,
                }
            })

        self.assertEqual(['invalid value for altitude "-666666"'],
                         ctx.exception.reasons)

        # invalid size
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'LOC',
                'ttl': 600,
                'value': {
                    'lat_degrees': 31,
                    'lat_minutes': 58,
                    'lat_seconds': 52.1,
                    'lat_direction': 'S',
                    'long_degrees': 115,
                    'long_minutes': 49,
                    'long_seconds': 11.7,
                    'long_direction': 'E',
                    'altitude': 20,
                    'size': 99999999.99,
                    'precision_horz': 10,
                    'precision_vert': 2,
                }
            })

        self.assertEqual(['invalid value for size "99999999.99"'],
                         ctx.exception.reasons)

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
        self.assertEqual(['missing preference'], ctx.exception.reasons)

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
        self.assertEqual(['invalid preference "nope"'], ctx.exception.reasons)

        # missing exchange
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'MX',
                'ttl': 600,
                'value': {
                    'preference': 10,
                }
            })
        self.assertEqual(['missing exchange'], ctx.exception.reasons)

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
        self.assertEqual(['MX value "foo.bar.com" missing trailing .'],
                         ctx.exception.reasons)

        # exchange must be a valid FQDN
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'MX',
                'ttl': 600,
                'value': {
                    'preference': 10,
                    'exchange': '100 foo.bar.com.'
                }
            })
        self.assertEqual(['Invalid MX exchange "100 foo.bar.com." is not a '
                          'valid FQDN.'], ctx.exception.reasons)

        # exchange can be a single `.`
        record = Record.new(self.zone, '', {
            'type': 'MX',
            'ttl': 600,
            'value': {
                'preference': 0,
                'exchange': '.'
            }
        })
        self.assertEqual('.', record.values[0].exchange)

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
            self.assertEqual([f'missing {k}'], ctx.exception.reasons)

        # non-int order
        v = dict(value)
        v['order'] = 'boo'
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'NAPTR',
                'ttl': 600,
                'value': v
            })
        self.assertEqual(['invalid order "boo"'], ctx.exception.reasons)

        # non-int preference
        v = dict(value)
        v['preference'] = 'who'
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'NAPTR',
                'ttl': 600,
                'value': v
            })
        self.assertEqual(['invalid preference "who"'], ctx.exception.reasons)

        # unrecognized flags
        v = dict(value)
        v['flags'] = 'X'
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'NAPTR',
                'ttl': 600,
                'value': v
            })
        self.assertEqual(['unrecognized flags "X"'], ctx.exception.reasons)

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
        self.assertEqual(['missing value(s)'], ctx.exception.reasons)

        # no trailing .
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'NS',
                'ttl': 600,
                'value': 'foo.bar',
            })
        self.assertEqual(['NS value "foo.bar" missing trailing .'],
                         ctx.exception.reasons)

        # exchange must be a valid FQDN
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'NS',
                'ttl': 600,
                'value': '100 foo.bar.com.'
            })
        self.assertEqual(['Invalid NS value "100 foo.bar.com." is not a '
                          'valid FQDN.'], ctx.exception.reasons)

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
        self.assertEqual(['missing values'], ctx.exception.reasons)

        # not a valid FQDN
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'PTR',
                'ttl': 600,
                'value': '_.',
            })
        self.assertEqual(['PTR value "_." is not a valid FQDN'],
                         ctx.exception.reasons)

        # no trailing .
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'PTR',
                'ttl': 600,
                'value': 'foo.bar',
            })
        self.assertEqual(['PTR value "foo.bar" missing trailing .'],
                         ctx.exception.reasons)

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
        self.assertEqual(['missing algorithm'], ctx.exception.reasons)

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
        self.assertEqual(['invalid algorithm "nope"'], ctx.exception.reasons)

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
        self.assertEqual(['unrecognized algorithm "42"'],
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
        self.assertEqual(['missing fingerprint_type'], ctx.exception.reasons)

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
        self.assertEqual(['invalid fingerprint_type "yeeah"'],
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
        self.assertEqual(['unrecognized fingerprint_type "42"'],
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
        self.assertEqual(['missing fingerprint'], ctx.exception.reasons)

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
        self.assertEqual(['missing value(s)'], ctx.exception.reasons)

        # missing escapes
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'SPF',
                'ttl': 600,
                'value': 'this has some; semi-colons\\; in it',
            })
        self.assertEqual(['unescaped ; in "this has some; '
                          'semi-colons\\; in it"'], ctx.exception.reasons)

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

        # permit wildcard entries
        Record.new(self.zone, '*._tcp', {
            'type': 'SRV',
            'ttl': 600,
            'value': {
                'priority': 1,
                'weight': 2,
                'port': 3,
                'target': 'food.bar.baz.'
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
        self.assertEqual(['invalid name for SRV record'],
                         ctx.exception.reasons)

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
        self.assertEqual(['missing priority'], ctx.exception.reasons)

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
        self.assertEqual(['invalid priority "foo"'], ctx.exception.reasons)

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
        self.assertEqual(['missing weight'], ctx.exception.reasons)
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
        self.assertEqual(['invalid weight "foo"'], ctx.exception.reasons)

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
        self.assertEqual(['missing port'], ctx.exception.reasons)
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
        self.assertEqual(['invalid port "foo"'], ctx.exception.reasons)

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
        self.assertEqual(['missing target'], ctx.exception.reasons)
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
        self.assertEqual(['SRV value "foo.bar.baz" missing trailing .'],
                         ctx.exception.reasons)

        # target must be a valid FQDN
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '_srv._tcp', {
                'type': 'SRV',
                'ttl': 600,
                'value': {
                    'priority': 1,
                    'weight': 2,
                    'port': 3,
                    'target': '100 foo.bar.com.'
                }
            })
        self.assertEqual(['Invalid SRV target "100 foo.bar.com." is not a '
                          'valid FQDN.'], ctx.exception.reasons)

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
        self.assertEqual(['missing value(s)'], ctx.exception.reasons)

        # missing escapes
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'TXT',
                'ttl': 600,
                'value': 'this has some; semi-colons\\; in it',
            })
        self.assertEqual(['unescaped ; in "this has some; semi-colons\\; '
                          'in it"'], ctx.exception.reasons)

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
        self.assertEqual(3, len(single.values))
        self.assertEqual(3, len(single.chunked_values))
        # Note we are checking that this normalizes the chunking, not that we
        # get out what we put in.
        self.assertEqual(expected, single.chunked_values[0])

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
        self.assertEqual(expected, chunked.chunked_values[0])
        # should be single values, no quoting
        self.assertEqual(single.values, chunked.values)
        # should be chunked values, with quoting
        self.assertEqual(single.chunked_values, chunked.chunked_values)

    def test_URLFWD(self):
        # doesn't blow up
        Record.new(self.zone, '', {
            'type': 'URLFWD',
            'ttl': 600,
            'value': {
                'path': '/',
                'target': 'http://foo',
                'code': 301,
                'masking': 2,
                'query': 0,
            }
        })
        Record.new(self.zone, '', {
            'type': 'URLFWD',
            'ttl': 600,
            'values': [{
                'path': '/',
                'target': 'http://foo',
                'code': 301,
                'masking': 2,
                'query': 0,
            }, {
                'path': '/target',
                'target': 'http://target',
                'code': 302,
                'masking': 2,
                'query': 0,
            }]
        })

        # missing path
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'URLFWD',
                'ttl': 600,
                'value': {
                    'target': 'http://foo',
                    'code': 301,
                    'masking': 2,
                    'query': 0,
                }
            })
        self.assertEqual(['missing path'], ctx.exception.reasons)

        # missing target
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'URLFWD',
                'ttl': 600,
                'value': {
                    'path': '/',
                    'code': 301,
                    'masking': 2,
                    'query': 0,
                }
            })
        self.assertEqual(['missing target'], ctx.exception.reasons)

        # missing code
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'URLFWD',
                'ttl': 600,
                'value': {
                    'path': '/',
                    'target': 'http://foo',
                    'masking': 2,
                    'query': 0,
                }
            })
        self.assertEqual(['missing code'], ctx.exception.reasons)

        # invalid code
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'URLFWD',
                'ttl': 600,
                'value': {
                    'path': '/',
                    'target': 'http://foo',
                    'code': 'nope',
                    'masking': 2,
                    'query': 0,
                }
            })
        self.assertEqual(['invalid return code "nope"'],
                         ctx.exception.reasons)

        # unrecognized code
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'URLFWD',
                'ttl': 600,
                'value': {
                    'path': '/',
                    'target': 'http://foo',
                    'code': 3,
                    'masking': 2,
                    'query': 0,
                }
            })
        self.assertEqual(['unrecognized return code "3"'],
                         ctx.exception.reasons)

        # missing masking
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'URLFWD',
                'ttl': 600,
                'value': {
                    'path': '/',
                    'target': 'http://foo',
                    'code': 301,
                    'query': 0,
                }
            })
        self.assertEqual(['missing masking'], ctx.exception.reasons)

        # invalid masking
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'URLFWD',
                'ttl': 600,
                'value': {
                    'path': '/',
                    'target': 'http://foo',
                    'code': 301,
                    'masking': 'nope',
                    'query': 0,
                }
            })
        self.assertEqual(['invalid masking setting "nope"'],
                         ctx.exception.reasons)

        # unrecognized masking
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'URLFWD',
                'ttl': 600,
                'value': {
                    'path': '/',
                    'target': 'http://foo',
                    'code': 301,
                    'masking': 3,
                    'query': 0,
                }
            })
        self.assertEqual(['unrecognized masking setting "3"'],
                         ctx.exception.reasons)

        # missing query
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'URLFWD',
                'ttl': 600,
                'value': {
                    'path': '/',
                    'target': 'http://foo',
                    'code': 301,
                    'masking': 2,
                }
            })
        self.assertEqual(['missing query'], ctx.exception.reasons)

        # invalid query
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'URLFWD',
                'ttl': 600,
                'value': {
                    'path': '/',
                    'target': 'http://foo',
                    'code': 301,
                    'masking': 2,
                    'query': 'nope',
                }
            })
        self.assertEqual(['invalid query setting "nope"'],
                         ctx.exception.reasons)

        # unrecognized query
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {
                'type': 'URLFWD',
                'ttl': 600,
                'value': {
                    'path': '/',
                    'target': 'http://foo',
                    'code': 301,
                    'masking': 2,
                    'query': 3,
                }
            })
        self.assertEqual(['unrecognized query setting "3"'],
                         ctx.exception.reasons)


class TestDynamicRecords(TestCase):
    zone = Zone('unit.tests.', [])

    def test_simple_a_weighted(self):
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'weight': 10,
                            'value': '3.3.3.3',
                        }],
                    },
                    'two': {
                        # Testing out of order value sorting here
                        'values': [{
                            'value': '5.5.5.5',
                        }, {
                            'value': '4.4.4.4',
                        }],
                    },
                    'three': {
                        'values': [{
                            'weight': 10,
                            'value': '4.4.4.4',
                        }, {
                            'weight': 12,
                            'value': '5.5.5.5',
                        }],
                    },
                },
                'rules': [{
                    'geos': ['AF', 'EU'],
                    'pool': 'three',
                }, {
                    'geos': ['NA-US-CA'],
                    'pool': 'two',
                }, {
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        a = ARecord(self.zone, 'weighted', a_data)
        self.assertEqual('A', a._type)
        self.assertEqual(a_data['ttl'], a.ttl)
        self.assertEqual(a_data['values'], a.values)

        dynamic = a.dynamic
        self.assertTrue(dynamic)

        pools = dynamic.pools
        self.assertTrue(pools)
        self.assertEqual({
            'value': '3.3.3.3',
            'weight': 1,
            'status': 'obey',
        }, pools['one'].data['values'][0])
        self.assertEqual([{
            'value': '4.4.4.4',
            'weight': 1,
            'status': 'obey',
        }, {
            'value': '5.5.5.5',
            'weight': 1,
            'status': 'obey',
        }], pools['two'].data['values'])
        self.assertEqual([{
            'weight': 10,
            'value': '4.4.4.4',
            'status': 'obey',
        }, {
            'weight': 12,
            'value': '5.5.5.5',
            'status': 'obey',
        }], pools['three'].data['values'])

        rules = dynamic.rules
        self.assertTrue(rules)
        self.assertEqual(a_data['dynamic']['rules'][0], rules[0].data)

        # smoke test of _DynamicMixin.__repr__
        a.__repr__()
        delattr(a, 'values')
        a.value = 'abc'
        a.__repr__()

    def test_simple_aaaa_weighted(self):
        aaaa_data = {
            'dynamic': {
                'pools': {
                    'one': '2601:642:500:e210:62f8:1dff:feb8:9473',
                    'two': [
                        '2601:642:500:e210:62f8:1dff:feb8:9474',
                        '2601:642:500:e210:62f8:1dff:feb8:9475',
                    ],
                    'three': {
                        1: '2601:642:500:e210:62f8:1dff:feb8:9476',
                        2: '2601:642:500:e210:62f8:1dff:feb8:9477',
                    },
                },
                'rules': [{
                    'pools': [
                        'three',
                        'two',
                        'one',
                    ],
                }],
            },
            'ttl': 60,
            'values': [
                '2601:642:500:e210:62f8:1dff:feb8:9471',
                '2601:642:500:e210:62f8:1dff:feb8:9472',
            ],
        }
        aaaa_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': '2601:642:500:e210:62f8:1dff:feb8:9473',
                        }],
                    },
                    'two': {
                        # Testing out of order value sorting here
                        'values': [{
                            'value': '2601:642:500:e210:62f8:1dff:feb8:9475',
                        }, {
                            'value': '2601:642:500:e210:62f8:1dff:feb8:9474',
                        }],
                    },
                    'three': {
                        'values': [{
                            'weight': 10,
                            'value': '2601:642:500:e210:62f8:1dff:feb8:9476',
                        }, {
                            'weight': 12,
                            'value': '2601:642:500:e210:62f8:1dff:feb8:9477',
                        }],
                    },
                },
                'rules': [{
                    'geos': ['AF', 'EU'],
                    'pool': 'three',
                }, {
                    'geos': ['NA-US-CA'],
                    'pool': 'two',
                }, {
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'values': [
                '2601:642:500:e210:62f8:1dff:feb8:9471',
                '2601:642:500:e210:62f8:1dff:feb8:9472',
            ],
        }
        aaaa = AaaaRecord(self.zone, 'weighted', aaaa_data)
        self.assertEqual('AAAA', aaaa._type)
        self.assertEqual(aaaa_data['ttl'], aaaa.ttl)
        self.assertEqual(aaaa_data['values'], aaaa.values)

        dynamic = aaaa.dynamic
        self.assertTrue(dynamic)

        pools = dynamic.pools
        self.assertTrue(pools)
        self.assertEqual({
            'value': '2601:642:500:e210:62f8:1dff:feb8:9473',
            'weight': 1,
            'status': 'obey',
        }, pools['one'].data['values'][0])
        self.assertEqual([{
            'value': '2601:642:500:e210:62f8:1dff:feb8:9474',
            'weight': 1,
            'status': 'obey',
        }, {
            'value': '2601:642:500:e210:62f8:1dff:feb8:9475',
            'weight': 1,
            'status': 'obey',
        }], pools['two'].data['values'])
        self.assertEqual([{
            'weight': 10,
            'value': '2601:642:500:e210:62f8:1dff:feb8:9476',
            'status': 'obey',
        }, {
            'weight': 12,
            'value': '2601:642:500:e210:62f8:1dff:feb8:9477',
            'status': 'obey',
        }], pools['three'].data['values'])

        rules = dynamic.rules
        self.assertTrue(rules)
        self.assertEqual(aaaa_data['dynamic']['rules'][0], rules[0].data)

    def test_simple_cname_weighted(self):
        cname_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': 'one.cname.target.',
                        }],
                    },
                    'two': {
                        'values': [{
                            'value': 'two.cname.target.',
                        }],
                    },
                    'three': {
                        'values': [{
                            'weight': 12,
                            'value': 'three-1.cname.target.',
                        }, {
                            'weight': 32,
                            'value': 'three-2.cname.target.',
                        }]
                    },
                },
                'rules': [{
                    'geos': ['AF', 'EU'],
                    'pool': 'three',
                }, {
                    'geos': ['NA-US-CA'],
                    'pool': 'two',
                }, {
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'value': 'cname.target.',
        }
        cname = CnameRecord(self.zone, 'weighted', cname_data)
        self.assertEqual('CNAME', cname._type)
        self.assertEqual(cname_data['ttl'], cname.ttl)
        self.assertEqual(cname_data['value'], cname.value)

        dynamic = cname.dynamic
        self.assertTrue(dynamic)

        pools = dynamic.pools
        self.assertTrue(pools)
        self.assertEqual({
            'value': 'one.cname.target.',
            'weight': 1,
            'status': 'obey',
        }, pools['one'].data['values'][0])
        self.assertEqual({
            'value': 'two.cname.target.',
            'weight': 1,
            'status': 'obey',
        }, pools['two'].data['values'][0])
        self.assertEqual([{
            'value': 'three-1.cname.target.',
            'weight': 12,
            'status': 'obey',
        }, {
            'value': 'three-2.cname.target.',
            'weight': 32,
            'status': 'obey',
        }], pools['three'].data['values'])

        rules = dynamic.rules
        self.assertTrue(rules)
        self.assertEqual(cname_data['dynamic']['rules'][0], rules[0].data)

    def test_dynamic_validation(self):
        # Missing pools
        a_data = {
            'dynamic': {
                'rules': [{
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(['missing pools', 'rule 1 undefined pool "one"'],
                         ctx.exception.reasons)

        # Empty pools
        a_data = {
            'dynamic': {
                'pools': {
                },
                'rules': [{
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(['missing pools', 'rule 1 undefined pool "one"'],
                         ctx.exception.reasons)

        # pools not a dict
        a_data = {
            'dynamic': {
                'pools': [],
                'rules': [{
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(['pools must be a dict',
                          'rule 1 undefined pool "one"'],
                         ctx.exception.reasons)

        # Invalid addresses
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': 'this-aint-right',
                        }],
                    },
                    'two': {
                        'fallback': 'one',
                        'values': [{
                            'value': '4.4.4.4',
                        }, {
                            'value': 'nor-is-this',
                        }]
                    },
                    'three': {
                        'fallback': 'two',
                        'values': [{
                            'weight': 1,
                            'value': '5.5.5.5',
                        }, {
                            'weight': 2,
                            'value': 'yet-another-bad-one',
                        }],
                    },
                },
                'rules': [{
                    'geos': ['AF', 'EU'],
                    'pool': 'three',
                }, {
                    'geos': ['NA-US-CA'],
                    'pool': 'two',
                }, {
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual([
            'invalid IPv4 address "this-aint-right"',
            'invalid IPv4 address "yet-another-bad-one"',
            'invalid IPv4 address "nor-is-this"',
        ], ctx.exception.reasons)

        # missing value(s)
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {},
                    'two': {
                        'values': [{
                            'value': '4.4.4.4',
                        }, {
                            'value': '5.5.5.5',
                        }]
                    },
                    'three': {
                        'values': [{
                            'weight': 1,
                            'value': '6.6.6.6',
                        }, {
                            'weight': 2,
                            'value': '7.7.7.7',
                        }],
                    },
                },
                'rules': [{
                    'geos': ['AF', 'EU'],
                    'pool': 'three',
                }, {
                    'geos': ['NA-US-CA'],
                    'pool': 'two',
                }, {
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(['pool "one" is missing values'],
                         ctx.exception.reasons)

        # pool value not a dict
        a_data = {
            'dynamic': {
                'pools': {
                    'one': '',
                    'two': {
                        'values': [{
                            'value': '4.4.4.4',
                        }, {
                            'value': '5.5.5.5',
                        }]
                    },
                    'three': {
                        'values': [{
                            'weight': 1,
                            'value': '6.6.6.6',
                        }, {
                            'weight': 2,
                            'value': '7.7.7.7',
                        }],
                    },
                },
                'rules': [{
                    'geos': ['AF', 'EU'],
                    'pool': 'three',
                }, {
                    'geos': ['NA-US-CA'],
                    'pool': 'two',
                }, {
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(['pool "one" must be a dict'],
                         ctx.exception.reasons)

        # empty pool value
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {},
                    'two': {
                        'values': [{
                            'value': '4.4.4.4',
                        }, {
                            'value': '5.5.5.5',
                        }]
                    },
                    'three': {
                        'values': [{
                            'weight': 1,
                            'value': '6.6.6.6',
                        }, {
                            'weight': 2,
                            'value': '7.7.7.7',
                        }],
                    },
                },
                'rules': [{
                    'geos': ['AF', 'EU'],
                    'pool': 'three',
                }, {
                    'geos': ['NA-US-CA'],
                    'pool': 'two',
                }, {
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(['pool "one" is missing values'],
                         ctx.exception.reasons)

        # invalid int weight
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': '3.3.3.3',
                        }]
                    },
                    'two': {
                        'values': [{
                            'value': '4.4.4.4',
                        }, {
                            'value': '5.5.5.5',
                        }]
                    },
                    'three': {
                        'values': [{
                            'weight': 1,
                            'value': '6.6.6.6',
                        }, {
                            'weight': 101,
                            'value': '7.7.7.7',
                        }],
                    },
                },
                'rules': [{
                    'geos': ['AF', 'EU'],
                    'pool': 'three',
                }, {
                    'geos': ['NA-US-CA'],
                    'pool': 'two',
                }, {
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(['invalid weight "101" in pool "three" value 2'],
                         ctx.exception.reasons)

        # invalid non-int weight
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': '3.3.3.3',
                        }]
                    },
                    'two': {
                        'values': [{
                            'value': '4.4.4.4',
                        }, {
                            'value': '5.5.5.5',
                        }]
                    },
                    'three': {
                        'values': [{
                            'weight': 1,
                            'value': '6.6.6.6',
                        }, {
                            'weight': 'foo',
                            'value': '7.7.7.7',
                        }],
                    },
                },
                'rules': [{
                    'geos': ['AF', 'EU'],
                    'pool': 'three',
                }, {
                    'geos': ['NA-US-CA'],
                    'pool': 'two',
                }, {
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(['invalid weight "foo" in pool "three" value 2'],
                         ctx.exception.reasons)

        # single value with weight!=1
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'weight': 12,
                            'value': '6.6.6.6',
                        }],
                    },
                },
                'rules': [{
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(['pool "one" has single value with weight!=1'],
                         ctx.exception.reasons)

        # invalid fallback
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': '3.3.3.3',
                        }],
                    },
                    'two': {
                        'fallback': 'invalid',
                        'values': [{
                            'value': '4.4.4.4',
                        }, {
                            'value': '5.5.5.5',
                        }]
                    },
                    'three': {
                        'fallback': 'two',
                        'values': [{
                            'weight': 1,
                            'value': '6.6.6.6',
                        }, {
                            'weight': 5,
                            'value': '7.7.7.7',
                        }],
                    },
                },
                'rules': [{
                    'geos': ['AF', 'EU'],
                    'pool': 'three',
                }, {
                    'geos': ['NA-US-CA'],
                    'pool': 'two',
                }, {
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(['undefined fallback "invalid" for pool "two"'],
                         ctx.exception.reasons)

        # fallback loop
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'fallback': 'three',
                        'values': [{
                            'value': '3.3.3.3',
                        }],
                    },
                    'two': {
                        'fallback': 'one',
                        'values': [{
                            'value': '4.4.4.4',
                        }, {
                            'value': '5.5.5.5',
                        }]
                    },
                    'three': {
                        'fallback': 'two',
                        'values': [{
                            'weight': 1,
                            'value': '6.6.6.6',
                        }, {
                            'weight': 5,
                            'value': '7.7.7.7',
                        }],
                    },
                },
                'rules': [{
                    'geos': ['AF', 'EU'],
                    'pool': 'three',
                }, {
                    'geos': ['NA-US-CA'],
                    'pool': 'two',
                }, {
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual([
            'loop in pool fallbacks: one -> three -> two',
            'loop in pool fallbacks: three -> two -> one',
            'loop in pool fallbacks: two -> one -> three'
        ], ctx.exception.reasons)

        # multiple pool problems
        a_data = {
            'dynamic': {
                'pools': {
                    'one': '',
                    'two': {
                        'values': [{
                            'value': '4.4.4.4',
                        }, {
                            'value': 'blip',
                        }]
                    },
                    'three': {
                        'values': [{
                            'weight': 1,
                        }, {
                            'weight': 5000,
                            'value': '7.7.7.7',
                        }],
                    },
                },
                'rules': [{
                    'geos': ['AF', 'EU'],
                    'pool': 'three',
                }, {
                    'geos': ['NA-US-CA'],
                    'pool': 'two',
                }, {
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual([
            'pool "one" must be a dict',
            'missing value in pool "three" value 1',
            'invalid weight "5000" in pool "three" value 2',
            'invalid IPv4 address "blip"',
        ], ctx.exception.reasons)

        # missing rules, and unused pools
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': '3.3.3.3',
                        }]
                    },
                    'two': {
                        'values': [{
                            'value': '4.4.4.4',
                        }, {
                            'value': '5.5.5.5',
                        }]
                    },
                },
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual([
            'missing rules',
            'unused pools: "one", "two"',
        ], ctx.exception.reasons)

        # empty rules
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': '3.3.3.3',
                        }]
                    },
                    'two': {
                        'values': [{
                            'value': '4.4.4.4',
                        }, {
                            'value': '5.5.5.5',
                        }]
                    },
                },
                'rules': [],
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual([
            'missing rules',
            'unused pools: "one", "two"',
        ], ctx.exception.reasons)

        # rules not a list/tuple
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': '3.3.3.3',
                        }]
                    },
                    'two': {
                        'values': [{
                            'value': '4.4.4.4',
                        }, {
                            'value': '5.5.5.5',
                        }]
                    },
                },
                'rules': {},
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual([
            'rules must be a list',
            'unused pools: "one", "two"',
        ], ctx.exception.reasons)

        # rule without pool
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': '3.3.3.3',
                        }],
                    },
                    'two': {
                        'values': [{
                            'value': '4.4.4.4',
                        }, {
                            'value': '5.5.5.5',
                        }]
                    },
                },
                'rules': [{
                    'geos': ['NA-US-CA'],
                }, {
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual([
            'rule 1 missing pool',
            'unused pools: "two"',
        ], ctx.exception.reasons)

        # rule with non-string pools
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': '3.3.3.3',
                        }]
                    },
                    'two': {
                        'values': [{
                            'value': '4.4.4.4',
                        }, {
                            'value': '5.5.5.5',
                        }]
                    },
                },
                'rules': [{
                    'geos': ['NA-US-CA'],
                    'pool': [],
                }, {
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual([
            'rule 1 invalid pool "[]"',
            'unused pools: "two"',
        ], ctx.exception.reasons)

        # rule references non-existent pool
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': '3.3.3.3',
                        }]
                    },
                    'two': {
                        'values': [{
                            'value': '4.4.4.4',
                        }, {
                            'value': '5.5.5.5',
                        }]
                    },
                },
                'rules': [{
                    'geos': ['NA-US-CA'],
                    'pool': 'non-existent',
                }, {
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual([
            "rule 1 undefined pool \"non-existent\"",
            'unused pools: "two"',
        ], ctx.exception.reasons)

        # rule with invalid geos
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': '3.3.3.3',
                        }]
                    },
                    'two': {
                        'values': [{
                            'value': '4.4.4.4',
                        }, {
                            'value': '5.5.5.5',
                        }]
                    },
                },
                'rules': [{
                    'geos': 'NA-US-CA',
                    'pool': 'two',
                }, {
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(['rule 1 geos must be a list'],
                         ctx.exception.reasons)

        # rule with invalid geo
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': '3.3.3.3',
                        }]
                    },
                    'two': {
                        'values': [{
                            'value': '4.4.4.4',
                        }, {
                            'value': '5.5.5.5',
                        }]
                    },
                },
                'rules': [{
                    'geos': ['invalid'],
                    'pool': 'two',
                }, {
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(['rule 1 unknown continent code "invalid"'],
                         ctx.exception.reasons)

        # multiple default rules
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': '3.3.3.3',
                        }]
                    },
                    'two': {
                        'values': [{
                            'value': '4.4.4.4',
                        }, {
                            'value': '5.5.5.5',
                        }]
                    },
                },
                'rules': [{
                    'pool': 'two',
                }, {
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(['rule 2 duplicate default'],
                         ctx.exception.reasons)

        # repeated pool in rules
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': '3.3.3.3',
                        }]
                    },
                    'two': {
                        'values': [{
                            'value': '4.4.4.4',
                        }, {
                            'value': '5.5.5.5',
                        }]
                    },
                },
                'rules': [{
                    'geos': ['EU'],
                    'pool': 'two',
                }, {
                    'geos': ['AF'],
                    'pool': 'one',
                }, {
                    'geos': ['OC'],
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(['rule 3 invalid, target pool "one" reused'],
                         ctx.exception.reasons)

        # Repeated pool is OK if later one is a default
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': '3.3.3.3',
                        }]
                    },
                    'two': {
                        'values': [{
                            'value': '4.4.4.4',
                        }, {
                            'value': '5.5.5.5',
                        }]
                    },
                },
                'rules': [{
                    'geos': ['EU-GB'],
                    'pool': 'one',
                }, {
                    'geos': ['EU'],
                    'pool': 'two',
                }, {
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        # This should be valid, no exception
        Record.new(self.zone, 'bad', a_data)

        # invalid status
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': '2.2.2.2',
                            'status': 'none',
                        }],
                    },
                },
                'rules': [{
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1'],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertIn('invalid status', ctx.exception.reasons[0])

    def test_dynamic_lenient(self):
        # Missing pools
        a_data = {
            'dynamic': {
                'rules': [{
                    'geos': ['EU'],
                    'pool': 'two',
                }, {
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        a = Record.new(self.zone, 'bad', a_data, lenient=True)
        self.assertEqual({
            'pools': {},
            'rules': a_data['dynamic']['rules'],
        }, a._data()['dynamic'])

        # Missing rule
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': '3.3.3.3',
                        }]
                    },
                    'two': {
                        'values': [{
                            'value': '4.4.4.4',
                        }, {
                            'value': '5.5.5.5',
                            'weight': 2,
                        }]
                    },
                },
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        a = Record.new(self.zone, 'bad', a_data, lenient=True)
        self.assertEqual({
            'pools': {
                'one': {
                    'fallback': None,
                    'values': [{
                        'value': '3.3.3.3',
                        'weight': 1,
                        'status': 'obey',
                    }]
                },
                'two': {
                    'fallback': None,
                    'values': [{
                        'value': '4.4.4.4',
                        'weight': 1,
                        'status': 'obey',
                    }, {
                        'value': '5.5.5.5',
                        'weight': 2,
                        'status': 'obey',
                    }]
                },
            },
            'rules': [],
        }, a._data()['dynamic'])

        # rule without pool
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': '3.3.3.3',
                        }]
                    },
                    'two': {
                        'values': [{
                            'value': '4.4.4.4',
                        }, {
                            'value': '5.5.5.5',
                            'weight': 2,
                        }]
                    },
                },
                'rules': [{
                    'geos': ['EU'],
                    'pool': 'two',
                }, {
                }],
            },
            'ttl': 60,
            'type': 'A',
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        a = Record.new(self.zone, 'bad', a_data, lenient=True)
        self.assertEqual({
            'pools': {
                'one': {
                    'fallback': None,
                    'values': [{
                        'value': '3.3.3.3',
                        'weight': 1,
                        'status': 'obey',
                    }]
                },
                'two': {
                    'fallback': None,
                    'values': [{
                        'value': '4.4.4.4',
                        'weight': 1,
                        'status': 'obey',
                    }, {
                        'value': '5.5.5.5',
                        'weight': 2,
                        'status': 'obey',
                    }]
                },
            },
            'rules': a_data['dynamic']['rules'],
        }, a._data()['dynamic'])

    def test_dynamic_changes(self):
        simple = SimpleProvider()
        dynamic = DynamicProvider()

        a_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': '3.3.3.3',
                        }]
                    },
                    'two': {
                        'values': [{
                            'value': '4.4.4.4',
                        }, {
                            'value': '5.5.5.5',
                        }]
                    },
                },
                'rules': [{
                    'geos': ['EU'],
                    'pool': 'two',
                }, {
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        a = ARecord(self.zone, 'weighted', a_data)
        dup = ARecord(self.zone, 'weighted', a_data)

        b_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': '3.3.3.3',
                        }]
                    },
                    'two': {
                        'values': [{
                            'value': '4.4.4.4',
                            'weight': 2,
                        }, {
                            'value': '5.5.5.5',
                        }]
                    },
                },
                'rules': [{
                    'geos': ['EU'],
                    'pool': 'two',
                }, {
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        b = ARecord(self.zone, 'weighted', b_data)

        c_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': '3.3.3.3',
                        }]
                    },
                    'two': {
                        'values': [{
                            'value': '4.4.4.4',
                        }, {
                            'value': '5.5.5.5',
                        }]
                    },
                },
                'rules': [{
                    'geos': ['NA'],
                    'pool': 'two',
                }, {
                    'pool': 'one',
                }],
            },
            'ttl': 60,
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        c = ARecord(self.zone, 'weighted', c_data)

        # a changes a (identical dup) is never true
        self.assertFalse(a.changes(dup, simple))
        self.assertFalse(a.changes(dup, dynamic))

        # a changes b is not true for simple
        self.assertFalse(a.changes(b, simple))
        # but is true for dynamic
        update = a.changes(b, dynamic)
        self.assertEqual(a, update.existing)
        self.assertEqual(b, update.new)
        # transitive
        self.assertFalse(b.changes(a, simple))
        update = b.changes(a, dynamic)
        self.assertEqual(a, update.existing)
        self.assertEqual(b, update.new)

        # same for a change c
        self.assertFalse(a.changes(c, simple))
        self.assertTrue(a.changes(c, dynamic))
        self.assertFalse(c.changes(a, simple))
        self.assertTrue(c.changes(a, dynamic))

        # smoke test some of the equiality bits
        self.assertEqual(a.dynamic.pools, a.dynamic.pools)
        self.assertEqual(a.dynamic.pools['one'], a.dynamic.pools['one'])
        self.assertNotEqual(a.dynamic.pools['one'], a.dynamic.pools['two'])
        self.assertEqual(a.dynamic.rules, a.dynamic.rules)
        self.assertEqual(a.dynamic.rules[0], a.dynamic.rules[0])
        self.assertNotEqual(a.dynamic.rules[0], c.dynamic.rules[0])

    def test_dynamic_and_geo_validation(self):
        a_data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': '3.3.3.3',
                        }],
                    },
                    'two': {
                        # Testing out of order value sorting here
                        'values': [{
                            'value': '5.5.5.5',
                        }, {
                            'value': '4.4.4.4',
                        }],
                    },
                    'three': {
                        'values': [{
                            'weight': 10,
                            'value': '4.4.4.4',
                        }, {
                            'weight': 12,
                            'value': '5.5.5.5',
                        }],
                    },
                },
                'rules': [{
                    'geos': ['AF', 'EU'],
                    'pool': 'three',
                }, {
                    'geos': ['NA-US-CA'],
                    'pool': 'two',
                }, {
                    'pool': 'one',
                }],
            },
            'geo': {
                'NA': ['1.2.3.5'],
                'NA-US': ['1.2.3.5', '1.2.3.6']
            },
            'type': 'A',
            'ttl': 60,
            'values': [
                '1.1.1.1',
                '2.2.2.2',
            ],
        }
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, 'bad', a_data)
        self.assertEqual(['"dynamic" record with "geo" content'],
                         ctx.exception.reasons)

    def test_dynamic_eqs(self):

        pool_one = _DynamicPool('one', {
            'values': [{
                'value': '1.2.3.4',
            }],
        })
        pool_two = _DynamicPool('two', {
            'values': [{
                'value': '1.2.3.5',
            }],
        })
        self.assertEqual(pool_one, pool_one)
        self.assertNotEqual(pool_one, pool_two)
        self.assertNotEqual(pool_one, 42)

        pools = {
            'one': pool_one,
            'two': pool_two,
        }
        rule_one = _DynamicRule(0, {
            'pool': 'one',
        })
        rule_two = _DynamicRule(1, {
            'pool': 'two',
        })
        self.assertEqual(rule_one, rule_one)
        self.assertNotEqual(rule_one, rule_two)
        self.assertNotEqual(rule_one, 42)
        rules = [
            rule_one,
            rule_two,
        ]

        dynamic = _Dynamic(pools, rules)
        other = _Dynamic({}, [])
        self.assertEqual(dynamic, dynamic)
        self.assertNotEqual(dynamic, other)
        self.assertNotEqual(dynamic, 42)


class TestChanges(TestCase):
    zone = Zone('unit.tests.', [])
    record_a_1 = Record.new(zone, '1', {
        'type': 'A',
        'ttl': 30,
        'value': '1.2.3.4',
    })
    record_a_2 = Record.new(zone, '2', {
        'type': 'A',
        'ttl': 30,
        'value': '1.2.3.4',
    })
    record_aaaa_1 = Record.new(zone, '1', {
        'type': 'AAAA',
        'ttl': 30,
        'value': '2601:644:500:e210:62f8:1dff:feb8:947a',
    })
    record_aaaa_2 = Record.new(zone, '2', {
        'type': 'AAAA',
        'ttl': 30,
        'value': '2601:644:500:e210:62f8:1dff:feb8:947a',
    })

    def test_sort_same_change_type(self):
        # expect things to be ordered by name and type since all the change
        # types are the same it doesn't matter
        changes = [
            Create(self.record_aaaa_1),
            Create(self.record_a_2),
            Create(self.record_a_1),
            Create(self.record_aaaa_2),
        ]
        self.assertEqual([
            Create(self.record_a_1),
            Create(self.record_aaaa_1),
            Create(self.record_a_2),
            Create(self.record_aaaa_2),
        ], sorted(changes))

    def test_sort_same_different_type(self):
        # this time the change type is the deciding factor, deletes come before
        # creates, and then updates. Things of the same type, go down the line
        # and sort by name, and then type
        changes = [
            Delete(self.record_aaaa_1),
            Create(self.record_aaaa_1),
            Update(self.record_aaaa_1, self.record_aaaa_1),
            Update(self.record_a_1, self.record_a_1),
            Create(self.record_a_1),
            Delete(self.record_a_1),
            Delete(self.record_aaaa_2),
            Create(self.record_aaaa_2),
            Update(self.record_aaaa_2, self.record_aaaa_2),
            Update(self.record_a_2, self.record_a_2),
            Create(self.record_a_2),
            Delete(self.record_a_2),
        ]
        self.assertEqual([
            Delete(self.record_a_1),
            Delete(self.record_aaaa_1),
            Delete(self.record_a_2),
            Delete(self.record_aaaa_2),
            Create(self.record_a_1),
            Create(self.record_aaaa_1),
            Create(self.record_a_2),
            Create(self.record_aaaa_2),
            Update(self.record_a_1, self.record_a_1),
            Update(self.record_aaaa_1, self.record_aaaa_1),
            Update(self.record_a_2, self.record_a_2),
            Update(self.record_aaaa_2, self.record_aaaa_2),
        ], sorted(changes))
