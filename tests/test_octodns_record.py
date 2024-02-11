#
#
#

from unittest import TestCase

from octodns.idna import idna_encode
from octodns.record import (
    AliasRecord,
    ARecord,
    CnameRecord,
    Create,
    Delete,
    MxValue,
    NsValue,
    Record,
    RecordException,
    Rr,
    SrvValue,
    TxtRecord,
    Update,
    ValidationError,
    ValuesMixin,
)
from octodns.record.base import unquote
from octodns.yaml import ContextDict
from octodns.zone import Zone


class TestRecord(TestCase):
    zone = Zone('unit.tests.', [])

    def test_registration(self):
        with self.assertRaises(RecordException) as ctx:
            Record.register_type(None, 'A')
        self.assertEqual(
            'Type "A" already registered by octodns.record.a.ARecord',
            str(ctx.exception),
        )

        class AaRecord(ValuesMixin, Record):
            _type = 'AA'
            _value_type = NsValue

        self.assertTrue('AA' not in Record.registered_types())

        Record.register_type(AaRecord)
        aa = Record.new(
            self.zone,
            'registered',
            {'ttl': 360, 'type': 'AA', 'value': 'does.not.matter.'},
        )
        self.assertEqual(AaRecord, aa.__class__)

        self.assertTrue('AA' in Record.registered_types())

    def test_lowering(self):
        record = ARecord(
            self.zone, 'MiXeDcAsE', {'ttl': 30, 'type': 'A', 'value': '1.2.3.4'}
        )
        self.assertEqual('mixedcase', record.name)

    def test_utf8(self):
        zone = Zone('natación.mx.', [])
        utf8 = 'niño'
        encoded = idna_encode(utf8)
        record = ARecord(
            zone, utf8, {'ttl': 30, 'type': 'A', 'value': '1.2.3.4'}
        )
        self.assertEqual(encoded, record.name)
        self.assertEqual(utf8, record.decoded_name)
        self.assertTrue(f'{encoded}.{zone.name}', record.fqdn)
        self.assertTrue(f'{utf8}.{zone.decoded_name}', record.decoded_fqdn)

    def test_utf8_values(self):
        zone = Zone('unit.tests.', [])
        utf8 = 'гэрбүл.mn.'
        encoded = idna_encode(utf8)

        # ALIAS
        record = Record.new(
            zone, '', {'type': 'ALIAS', 'ttl': 300, 'value': utf8}
        )
        self.assertEqual(encoded, record.value)

        # CNAME
        record = Record.new(
            zone, 'cname', {'type': 'CNAME', 'ttl': 300, 'value': utf8}
        )
        self.assertEqual(encoded, record.value)

        # DNAME
        record = Record.new(
            zone, 'dname', {'type': 'DNAME', 'ttl': 300, 'value': utf8}
        )
        self.assertEqual(encoded, record.value)

        # MX
        record = Record.new(
            zone,
            'mx',
            {
                'type': 'MX',
                'ttl': 300,
                'value': {'preference': 10, 'exchange': utf8},
            },
        )
        self.assertEqual(
            MxValue({'preference': 10, 'exchange': encoded}), record.values[0]
        )

        # NS
        record = Record.new(
            zone, 'ns', {'type': 'NS', 'ttl': 300, 'value': utf8}
        )
        self.assertEqual(encoded, record.values[0])

        # PTR
        another_utf8 = 'niño.mx.'
        another_encoded = idna_encode(another_utf8)
        record = Record.new(
            zone,
            'ptr',
            {'type': 'PTR', 'ttl': 300, 'values': [utf8, another_utf8]},
        )
        self.assertEqual([encoded, another_encoded], record.values)

        # SRV
        record = Record.new(
            zone,
            '_srv._tcp',
            {
                'type': 'SRV',
                'ttl': 300,
                'value': {
                    'priority': 0,
                    'weight': 10,
                    'port': 80,
                    'target': utf8,
                },
            },
        )
        self.assertEqual(
            SrvValue(
                {'priority': 0, 'weight': 10, 'port': 80, 'target': encoded}
            ),
            record.values[0],
        )

    def test_from_rrs(self):
        # also tests ValuesMixin.data_from_rrs and ValueMixin.data_from_rrs
        rrs = (
            Rr('unit.tests.', 'A', 42, '1.2.3.4'),
            Rr('unit.tests.', 'AAAA', 43, 'fc00::1'),
            Rr('www.unit.tests.', 'A', 44, '3.4.5.6'),
            Rr('unit.tests.', 'A', 42, '2.3.4.5'),
            Rr('cname.unit.tests.', 'CNAME', 46, 'target.unit.tests.'),
            Rr('unit.tests.', 'AAAA', 43, 'fc00::0002'),
            Rr('www.unit.tests.', 'AAAA', 45, 'fc00::3'),
        )

        zone = Zone('unit.tests.', [])
        records = {
            (r._type, r.name): r for r in Record.from_rrs(zone, rrs, source=99)
        }
        record = records[('A', '')]
        self.assertEqual(42, record.ttl)
        self.assertEqual(['1.2.3.4', '2.3.4.5'], record.values)
        self.assertEqual(99, record.source)
        record = records[('AAAA', '')]
        self.assertEqual(43, record.ttl)
        self.assertEqual(['fc00::1', 'fc00::2'], record.values)
        record = records[('A', 'www')]
        self.assertEqual(44, record.ttl)
        self.assertEqual(['3.4.5.6'], record.values)
        record = records[('AAAA', 'www')]
        self.assertEqual(45, record.ttl)
        self.assertEqual(['fc00::3'], record.values)
        record = records[('CNAME', 'cname')]
        self.assertEqual(46, record.ttl)
        self.assertEqual('target.unit.tests.', record.value)
        # make sure there's nothing extra
        self.assertEqual(5, len(records))

    def test_parse_rdata_texts(self):
        self.assertEqual(['2.3.4.5'], ARecord.parse_rdata_texts(['2.3.4.5']))
        self.assertEqual(
            ['2.3.4.6', '3.4.5.7'],
            ARecord.parse_rdata_texts(['2.3.4.6', '3.4.5.7']),
        )
        self.assertEqual(
            ['some.target.'], CnameRecord.parse_rdata_texts(['some.target.'])
        )
        self.assertEqual(
            ['some.target.', 'other.target.'],
            CnameRecord.parse_rdata_texts(['some.target.', 'other.target.']),
        )

    def test_values_mixin_data(self):
        # empty values -> empty values in data
        a = ARecord(self.zone, '', {'type': 'A', 'ttl': 600, 'values': []})
        self.assertEqual([], a.data['values'])

        # empty value, no value or values in data
        b = ARecord(self.zone, '', {'type': 'A', 'ttl': 600, 'values': ['']})
        self.assertNotIn('value', b.data)

        # empty/None values -> empty values in data
        c = ARecord(
            self.zone, '', {'type': 'A', 'ttl': 600, 'values': ['', None]}
        )
        self.assertEqual([], a.data['values'])

        # empty/None values and valid, value in data
        c = ARecord(
            self.zone,
            '',
            {'type': 'A', 'ttl': 600, 'values': ['', None, '10.10.10.10']},
        )
        self.assertNotIn('values', c.data)
        self.assertEqual('10.10.10.10', c.data['value'])

    def test_value_mixin_data(self):
        # unspecified value, no value in data
        a = AliasRecord(
            self.zone, '', {'type': 'ALIAS', 'ttl': 600, 'value': None}
        )
        self.assertIsNone(a.data['value'])

        # unspecified value, no value in data
        a = AliasRecord(
            self.zone, '', {'type': 'ALIAS', 'ttl': 600, 'value': ''}
        )
        self.assertIsNone(a.data['value'])

    def test_record_new(self):
        txt = Record.new(
            self.zone, 'txt', {'ttl': 44, 'type': 'TXT', 'value': 'some text'}
        )
        self.assertIsInstance(txt, TxtRecord)
        self.assertEqual('TXT', txt._type)
        self.assertEqual(['some text'], txt.values)

        # Missing type
        with self.assertRaises(Exception) as ctx:
            Record.new(self.zone, 'unknown', {})
        self.assertTrue('missing type' in str(ctx.exception))

        # Unknown type
        with self.assertRaises(Exception) as ctx:
            Record.new(self.zone, 'unknown', {'type': 'XXX'})
        self.assertTrue('Unknown record type' in str(ctx.exception))

    def test_record_new_with_values_and_value(self):
        a = Record.new(
            self.zone,
            'a',
            {
                'ttl': 44,
                'type': 'A',
                'value': '1.2.3.4',
                'values': ['2.3.4.5', '3.4.5.6'],
            },
        )
        # values is preferred over value when both exist
        self.assertEqual(['2.3.4.5', '3.4.5.6'], a.values)

    def test_record_copy(self):
        a = Record.new(
            self.zone, 'a', {'ttl': 44, 'type': 'A', 'value': '1.2.3.4'}
        )

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
        d_data = {'ttl': 600, 'values': ['just a test']}
        d = TxtRecord(self.zone, 'txt', d_data)
        d.copy()
        self.assertEqual('TXT', d._type)

    def test_record_octodns_with_data_and_copy(self):
        a = Record.new(
            self.zone,
            'a',
            {
                'ttl': 44,
                'type': 'A',
                'value': '1.2.3.4',
                'octodns': {'first': 'level', 'key': {'second': 'level'}},
            },
        )

        # make a copy
        b = a.copy()
        # ensure they're ==
        self.assertEqual(a.data, b.data)

        # modifying b.data's result doesn't change b's actual data
        b_data = b.data
        b_data['added'] = 'thing'
        # dict is a deep copy
        b_data['octodns']['added'] = 'thing'
        b_data['octodns']['key']['added'] = 'thing'
        self.assertEqual(a.data, b.data)

        # rest of these will use copy, which relies on data for most of the
        # heavy lifting

        # hand add something at the first level of the copy
        b = a.copy()
        b.octodns['added'] = 'thing'
        b_data = b.data
        self.assertNotEqual(a.data, b_data)

        # hand modify something at the first level of the copy
        b = a.copy()
        b.octodns['first'] = 'unlevel'
        self.assertNotEqual(a.data, b.data)

        # delete something at the first level of the copy
        b = a.copy()
        del b.octodns['first']
        self.assertNotEqual(a.data, b.data)

        # hand add something deeper in the copy
        b = a.copy()
        b.octodns['key']['added'] = 'thing'
        self.assertNotEqual(a.data, b.data)

        # hand modify something deeper in the copy
        b = a.copy()
        b.octodns['key']['second'] = 'unlevel'
        self.assertNotEqual(a.data, b.data)

        # hand delete something deeper in the copy
        b = a.copy()
        del b.octodns['key']['second']
        self.assertNotEqual(a.data, b.data)

    def test_record_copy_with_no_values(self):
        txt = Record.new(
            self.zone,
            'txt',
            {'ttl': 45, 'type': 'TXT', 'values': []},
            lenient=True,
        )

        dup = txt.copy()
        self.assertEqual(txt.values, dup.values)

        cname = Record.new(
            self.zone,
            'cname',
            {'ttl': 45, 'type': 'CNAME', 'value': ''},
            lenient=True,
        )

        dup = cname.copy()
        self.assertEqual(cname.value, dup.value)

    def test_change(self):
        existing = Record.new(
            self.zone, 'txt', {'ttl': 44, 'type': 'TXT', 'value': 'some text'}
        )
        new = Record.new(
            self.zone, 'txt', {'ttl': 44, 'type': 'TXT', 'value': 'some change'}
        )
        create = Create(new)
        self.assertEqual(new.values, create.record.values)
        update = Update(existing, new)
        self.assertEqual(new.values, update.record.values)
        delete = Delete(existing)
        self.assertEqual(existing.values, delete.record.values)

    def test_inored(self):
        new = Record.new(
            self.zone,
            'txt',
            {
                'ttl': 44,
                'type': 'TXT',
                'value': 'some change',
                'octodns': {'ignored': True},
            },
        )
        self.assertTrue(new.ignored)
        new = Record.new(
            self.zone,
            'txt',
            {
                'ttl': 44,
                'type': 'TXT',
                'value': 'some change',
                'octodns': {'ignored': False},
            },
        )
        self.assertFalse(new.ignored)
        new = Record.new(
            self.zone, 'txt', {'ttl': 44, 'type': 'TXT', 'value': 'some change'}
        )
        self.assertFalse(new.ignored)

    def test_ordering_functions(self):
        a = Record.new(
            self.zone, 'a', {'ttl': 44, 'type': 'A', 'value': '1.2.3.4'}
        )
        b = Record.new(
            self.zone, 'b', {'ttl': 44, 'type': 'A', 'value': '1.2.3.4'}
        )
        c = Record.new(
            self.zone, 'c', {'ttl': 44, 'type': 'A', 'value': '1.2.3.4'}
        )
        aaaa = Record.new(
            self.zone,
            'a',
            {
                'ttl': 44,
                'type': 'AAAA',
                'value': '2601:644:500:e210:62f8:1dff:feb8:947a',
            },
        )

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

    def test_rr(self):
        # nothing much to test, just make sure that things don't blow up
        Rr('name', 'type', 42, 'Hello World!').__repr__()

        zone = Zone('unit.tests.', [])
        record = Record.new(
            zone,
            'a',
            {'ttl': 42, 'type': 'A', 'values': ['1.2.3.4', '2.3.4.5']},
        )
        self.assertEqual(
            ('a.unit.tests.', 42, 'A', ['1.2.3.4', '2.3.4.5']), record.rrs
        )

        record = Record.new(
            zone,
            'cname',
            {'ttl': 43, 'type': 'CNAME', 'value': 'target.unit.tests.'},
        )
        self.assertEqual(
            ('cname.unit.tests.', 43, 'CNAME', ['target.unit.tests.']),
            record.rrs,
        )

    def test_unquote(self):
        s = 'Hello "\'"World!'
        single = f"'{s}'"
        double = f'"{s}"'
        self.assertEqual(s, unquote(s))
        self.assertEqual(s, unquote(single))
        self.assertEqual(s, unquote(double))

        # edge cases
        self.assertEqual(None, unquote(None))
        self.assertEqual('', unquote(''))

    def test_otodns_backcompat(self):
        octo = {'answer': 42}
        record = Record.new(
            self.zone,
            'www',
            {'ttl': 42, 'type': 'A', 'value': '1.2.3.4', 'octodns': octo},
        )
        self.assertEqual(octo, record.octodns)
        self.assertEqual(octo, record._octodns)

        octo2 = {'question': 'unknown'}
        record.octodns = octo2
        self.assertEqual(octo2, record.octodns)
        self.assertEqual(octo2, record._octodns)

        octo3 = {'key': 'val'}
        record._octodns = octo3
        self.assertEqual(octo3, record.octodns)
        self.assertEqual(octo3, record._octodns)


class TestRecordValidation(TestCase):
    zone = Zone('unit.tests.', [])

    def test_base(self):
        # no spaces
        for name in (
            ' ',
            ' leading',
            'trailing ',
            'in the middle',
            '\t',
            '\tleading',
            'trailing\t',
            'in\tthe\tmiddle',
        ):
            with self.assertRaises(ValidationError) as ctx:
                Record.new(
                    self.zone,
                    name,
                    {'ttl': 300, 'type': 'A', 'value': '1.2.3.4'},
                )
            reason = ctx.exception.reasons[0]
            self.assertEqual(
                'invalid record, whitespace is not allowed', reason
            )

        # name = '@'
        with self.assertRaises(ValidationError) as ctx:
            name = '@'
            Record.new(
                self.zone, name, {'ttl': 300, 'type': 'A', 'value': '1.2.3.4'}
            )
        reason = ctx.exception.reasons[0]
        self.assertTrue(reason.startswith('invalid name "@", use "" instead'))

        # fqdn length, DNS defines max as 253
        with self.assertRaises(ValidationError) as ctx:
            # The . will put this over the edge
            name = 'x' * (253 - len(self.zone.name))
            Record.new(
                self.zone, name, {'ttl': 300, 'type': 'A', 'value': '1.2.3.4'}
            )
        reason = ctx.exception.reasons[0]
        self.assertTrue(reason.startswith('invalid fqdn, "xxxx'))
        self.assertTrue(
            reason.endswith(
                '.unit.tests." is too long at 254 chars, max is 253'
            )
        )

        # label length, DNS defines max as 63
        with self.assertRaises(ValidationError) as ctx:
            # The . will put this over the edge
            name = 'x' * 64
            Record.new(
                self.zone, name, {'ttl': 300, 'type': 'A', 'value': '1.2.3.4'}
            )
        reason = ctx.exception.reasons[0]
        self.assertTrue(reason.startswith('invalid label, "xxxx'))
        self.assertTrue(
            reason.endswith('xxx" is too long at 64 chars, max is 63')
        )

        with self.assertRaises(ValidationError) as ctx:
            name = 'foo.' + 'x' * 64 + '.bar'
            Record.new(
                self.zone, name, {'ttl': 300, 'type': 'A', 'value': '1.2.3.4'}
            )
        reason = ctx.exception.reasons[0]
        self.assertTrue(reason.startswith('invalid label, "xxxx'))
        self.assertTrue(
            reason.endswith('xxx" is too long at 64 chars, max is 63')
        )

        # should not raise with dots
        name = 'xxxxxxxx.' * 10
        Record.new(
            self.zone, name, {'ttl': 300, 'type': 'A', 'value': '1.2.3.4'}
        )

        # make sure we're validating with encoded fqdns
        utf8 = 'déjà-vu'
        padding = ('.' + ('x' * 57)) * 4
        utf8_name = f'{utf8}{padding}'
        # make sure our test is valid here, we're under 253 chars long as utf8
        self.assertEqual(251, len(f'{utf8_name}.{self.zone.name}'))
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                utf8_name,
                {'ttl': 300, 'type': 'A', 'value': '1.2.3.4'},
            )
        reason = ctx.exception.reasons[0]
        self.assertTrue(reason.startswith('invalid fqdn, "déjà-vu'))
        self.assertTrue(
            reason.endswith(
                '.unit.tests." is too long at 259' ' chars, max is 253'
            )
        )

        # same, but with ascii version of things
        plain = 'deja-vu'
        plain_name = f'{plain}{padding}'
        self.assertEqual(251, len(f'{plain_name}.{self.zone.name}'))
        Record.new(
            self.zone, plain_name, {'ttl': 300, 'type': 'A', 'value': '1.2.3.4'}
        )

        # check that we're validating encoded labels
        padding = 'x' * (60 - len(utf8))
        utf8_name = f'{utf8}{padding}'
        # make sure the test is valid, we're at 63 chars
        self.assertEqual(60, len(utf8_name))
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                utf8_name,
                {'ttl': 300, 'type': 'A', 'value': '1.2.3.4'},
            )
        reason = ctx.exception.reasons[0]
        # Unfortunately this is a translated IDNAError so we don't have much
        # control over the exact message :-/ (doesn't give context like octoDNS
        # does)
        self.assertEqual('Label too long', reason)

        # no ttl
        with self.assertRaises(ValidationError) as ctx:
            Record.new(self.zone, '', {'type': 'A', 'value': '1.2.3.4'})
        self.assertEqual(['missing ttl'], ctx.exception.reasons)

        # invalid ttl
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone, 'www', {'type': 'A', 'ttl': -1, 'value': '1.2.3.4'}
            )
        self.assertEqual('www.unit.tests.', ctx.exception.fqdn)
        self.assertEqual(['invalid ttl'], ctx.exception.reasons)

        # no exception if we're in lenient mode
        Record.new(
            self.zone,
            'www',
            {'type': 'A', 'ttl': -1, 'value': '1.2.3.4'},
            lenient=True,
        )

        # empty values is allowed with lenient
        r = Record.new(self.zone, 'www', {'type': 'A', 'ttl': -1}, lenient=True)
        self.assertEqual([], r.values)

        # no exception if we're in lenient mode from config
        Record.new(
            self.zone,
            'www',
            {
                'octodns': {'lenient': True},
                'type': 'A',
                'ttl': -1,
                'value': '1.2.3.4',
            },
            lenient=True,
        )

    def test_values_and_value(self):
        # value w/one
        r = Record.new(
            self.zone, 'thing', {'type': 'TXT', 'ttl': 42, 'value': 'just one'}
        )
        self.assertEqual(['just one'], r.values)

        # value w/multiple
        r = Record.new(
            self.zone,
            'thing',
            {'type': 'TXT', 'ttl': 42, 'value': ['the first', 'the second']},
        )
        self.assertEqual(['the first', 'the second'], r.values)

        # values w/one
        r = Record.new(
            self.zone, 'thing', {'type': 'TXT', 'ttl': 42, 'values': 'just one'}
        )
        self.assertEqual(['just one'], r.values)

        # values w/multiple
        r = Record.new(
            self.zone,
            'thing',
            {'type': 'TXT', 'ttl': 42, 'values': ['the first', 'the second']},
        )
        self.assertEqual(['the first', 'the second'], r.values)

        # tuples work too
        r = Record.new(
            self.zone,
            'thing',
            {'type': 'TXT', 'ttl': 42, 'values': ('the first', 'the second')},
        )
        self.assertEqual(['the first', 'the second'], r.values)

        # values is preferred over value
        # values w/multiple
        r = Record.new(
            self.zone,
            'thing',
            {
                'type': 'TXT',
                'ttl': 42,
                'values': ['the first', 'the second'],
                'value': ['not used', 'not used'],
            },
        )
        self.assertEqual(['the first', 'the second'], r.values)

    def test_validation_context(self):
        # fails validation, no context
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone, 'www', {'type': 'A', 'ttl': -1, 'value': '1.2.3.4'}
            )
        self.assertFalse(', line' in str(ctx.exception))

        # fails validation, with context
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'www',
                ContextDict(
                    {'type': 'A', 'ttl': -1, 'value': '1.2.3.4'},
                    context='needle',
                ),
            )
        self.assertTrue('needle' in str(ctx.exception))

    def test_invalid_type_context(self):
        # fails validation, no context
        with self.assertRaises(Exception) as ctx:
            Record.new(
                self.zone, 'www', {'type': 'X', 'ttl': 42, 'value': '1.2.3.4'}
            )
        self.assertFalse(', line' in str(ctx.exception))

        # fails validation, with context
        with self.assertRaises(Exception) as ctx:
            Record.new(
                self.zone,
                'www',
                ContextDict(
                    {'type': 'X', 'ttl': 42, 'value': '1.2.3.4'},
                    context='needle',
                ),
            )
        self.assertTrue('needle' in str(ctx.exception))

    def test_missing_type_context(self):
        # fails validation, no context
        with self.assertRaises(Exception) as ctx:
            Record.new(self.zone, 'www', {'ttl': 42, 'value': '1.2.3.4'})
        self.assertFalse(', line' in str(ctx.exception))

        # fails validation, with context
        with self.assertRaises(Exception) as ctx:
            Record.new(
                self.zone,
                'www',
                ContextDict({'ttl': 42, 'value': '1.2.3.4'}, context='needle'),
            )
        self.assertTrue('needle' in str(ctx.exception))

    def test_context_copied_to_record(self):
        record = Record.new(
            self.zone,
            'www',
            ContextDict(
                {'ttl': 42, 'type': 'A', 'value': '1.2.3.4'}, context='needle'
            ),
        )
        self.assertEqual('needle', record.context)

    def test_values_mixin_repr(self):
        # ValuesMixin
        record = Record.new(
            self.zone,
            'www',
            {
                'ttl': 42,
                'type': 'A',
                'values': ['1.2.3.4', '2.3.4.5'],
                'octodns': {'key': 'value'},
            },
        )
        # has the octodns special section
        self.assertEqual(
            "<ARecord A 42, www.unit.tests., ['1.2.3.4', '2.3.4.5'], {'key': 'value'}>",
            record.__repr__(),
        )
        # no special section
        record.octodns = {}
        self.assertEqual(
            "<ARecord A 42, www.unit.tests., ['1.2.3.4', '2.3.4.5']>",
            record.__repr__(),
        )

    def test_value_mixin_repr(self):
        # ValueMixin
        record = Record.new(
            self.zone,
            'pointer',
            {
                'ttl': 43,
                'type': 'CNAME',
                'value': 'unit.tests.',
                'octodns': {'key': 42},
            },
        )
        # has the octodns special section
        self.assertEqual(
            "<CnameRecord CNAME 43, pointer.unit.tests., unit.tests., {'key': 42}>",
            record.__repr__(),
        )
        # no special section
        record.octodns = {}
        self.assertEqual(
            '<CnameRecord CNAME 43, pointer.unit.tests., unit.tests.>',
            record.__repr__(),
        )

    def test_records_have_rdata_methods(self):
        for _type, cls in Record.registered_types().items():
            print(f'{_type} {cls}')
            attr = 'parse_rdata_texts'
            print(f'  {attr}')
            method = getattr(cls, attr)
            self.assertTrue(method, f'{_type}, {cls} has {attr}')
            self.assertTrue(
                callable(method), f'{_type}, {cls} {attr} is callable'
            )

            value_type = getattr(cls, '_value_type')
            self.assertTrue(value_type, f'{_type}, {cls} has _value_type')

            attr = 'parse_rdata_text'
            print(f'  {attr}')
            method = getattr(value_type, attr)
            self.assertTrue(method, f'{_type}, {cls} has {attr}')
            self.assertTrue(
                callable(method), f'{_type}, {cls} {attr} is callable'
            )

            attr = 'rdata_text'
            method = getattr(value_type, attr)
            self.assertTrue(method, f'{_type}, {cls} has {attr}')
            # this one is a @property so not callable
