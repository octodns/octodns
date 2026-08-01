#
#
#

import warnings
from inspect import currentframe
from unittest import TestCase
from unittest.mock import patch

from octodns.idna import idna_encode
from octodns.record import (
    AliasRecord,
    ARecord,
    CnameRecord,
    Create,
    Delete,
    Ipv4Value,
    MxValue,
    NsValue,
    RdataParseError,
    Record,
    RecordException,
    Rr,
    RrParseError,
    Rrset,
    SrvValue,
    TxtRecord,
    Update,
    ValidationError,
    ValuesMixin,
)
from octodns.record import base as record_base
from octodns.record import value_from_rdata_text, value_to_rdata_text
from octodns.record.base import unquote
from octodns.yaml import ContextDict
from octodns.zone import Zone


class TestRecord(TestCase):
    zone = Zone('unit.tests.', [])

    def test_legacy_value_rr_api_fallback(self):
        class LegacyValue(str):
            @classmethod
            def process(cls, values):
                return [cls(value) for value in values]

            @classmethod
            def parse_rdata_text(cls, value):
                return value.upper()

            @property
            def rdata_text(self):
                return self.lower()

        class LegacyRecord(ValuesMixin, Record):
            _type = 'LEGACYRR'
            _value_type = LegacyValue

        Record.register_type(LegacyRecord)
        record = LegacyRecord(
            self.zone, 'legacy', {'ttl': 30, 'values': ['VALUE']}
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            self.assertEqual(
                ('legacy.unit.tests.', 30, 'LEGACYRR', ['value']), record.rrs
            )
            self.assertEqual(
                record.data,
                Record.from_rrs(
                    self.zone,
                    [Rr('legacy.unit.tests.', 'LEGACYRR', 30, 'value')],
                )[0].data,
            )
        self.assertEqual(
            [
                '`LegacyValue.rdata_text` is DEPRECATED. Implement '
                '`to_rdata_text()` instead. Will be removed in 2.0.',
                '`LegacyValue.parse_rdata_text` is DEPRECATED. Implement '
                '`from_rdata_text()` instead. Will be removed in 2.0.',
            ],
            [
                str(warning.message)
                for warning in caught
                if 'LegacyValue' in str(warning.message)
            ],
        )

    def test_value_rdata_mro_dispatch(self):
        class ParseOnlyValue(Ipv4Value):
            @classmethod
            def parse_rdata_text(cls, value):
                return '192.0.2.2'

        class ParseOnlyRecord(ValuesMixin, Record):
            _type = 'PARSEONLY'
            _value_type = ParseOnlyValue

        class RenderOnlyValue(Ipv4Value):
            @property
            def rdata_text(self):
                return '192.0.2.3'

        class RenderOnlyRecord(ValuesMixin, Record):
            _type = 'RENDERONLY'
            _value_type = RenderOnlyValue

        class IntermediateValue(Ipv4Value):
            @classmethod
            def parse_rdata_text(cls, value):
                return '192.0.2.4'

        class InheritedValue(IntermediateValue):
            pass

        class InheritedRecord(ValuesMixin, Record):
            _type = 'INHERITEDOLD'
            _value_type = InheritedValue

        class BothValue(Ipv4Value):
            @classmethod
            def parse_rdata_text(cls, value):
                return '192.0.2.5'

            @classmethod
            def from_rdata_text(cls, value):
                return '192.0.2.6'

            @property
            def rdata_text(self):
                return '192.0.2.7'

            def to_rdata_text(self):
                return '192.0.2.8'

        class BothRecord(ValuesMixin, Record):
            _type = 'BOTHAPIS'
            _value_type = BothValue

        class ExplicitNewValue(IntermediateValue):
            @classmethod
            def from_rdata_text(cls, value):
                return '192.0.2.9'

        class ExplicitNewRecord(ValuesMixin, Record):
            _type = 'EXPLICITNEW'
            _value_type = ExplicitNewValue

        for record_class in (
            ParseOnlyRecord,
            RenderOnlyRecord,
            InheritedRecord,
            BothRecord,
            ExplicitNewRecord,
        ):
            Record.register_type(record_class)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            record = Record.from_rrset(
                self.zone,
                Rrset('parse.unit.tests.', 'PARSEONLY', 30, ['192.0.2.1']),
            )
        self.assertEqual(['192.0.2.2'], record.values)
        self.assertEqual(
            '`ParseOnlyValue.parse_rdata_text` is DEPRECATED. Implement '
            '`from_rdata_text()` instead. Will be removed in 2.0.',
            str(caught[0].message),
        )
        self.assertTrue(caught[0].filename.endswith('/octodns/record/base.py'))

        record = RenderOnlyRecord(
            self.zone, 'render', {'ttl': 30, 'values': ['192.0.2.1']}
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            rrset = record.to_rrset()
        self.assertEqual(['192.0.2.3'], rrset.rdatas)
        self.assertEqual(
            '`RenderOnlyValue.rdata_text` is DEPRECATED. Implement '
            '`to_rdata_text()` instead. Will be removed in 2.0.',
            str(caught[0].message),
        )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            record = Record.from_rrset(
                self.zone,
                Rrset(
                    'inherited.unit.tests.', 'INHERITEDOLD', 30, ['192.0.2.1']
                ),
            )
        self.assertEqual(['192.0.2.4'], record.values)
        self.assertEqual(
            '`InheritedValue.parse_rdata_text` is DEPRECATED. Implement '
            '`from_rdata_text()` instead. Will be removed in 2.0.',
            str(caught[0].message),
        )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            both = Record.from_rrset(
                self.zone,
                Rrset('both.unit.tests.', 'BOTHAPIS', 30, ['192.0.2.1']),
            )
            both_rrset = both.to_rrset()
            explicit = Record.from_rrset(
                self.zone,
                Rrset('new.unit.tests.', 'EXPLICITNEW', 30, ['192.0.2.1']),
            )
        self.assertEqual(['192.0.2.6'], both.values)
        self.assertEqual(['192.0.2.8'], both_rrset.rdatas)
        self.assertEqual(['192.0.2.9'], explicit.values)
        self.assertEqual(
            [],
            [warning for warning in caught if 'Value.' in str(warning.message)],
        )

    def test_value_rdata_mro_dispatch_caching(self):
        class LegacyValue(Ipv4Value):
            @classmethod
            def parse_rdata_text(cls, value):
                return '192.0.2.2'

            @property
            def rdata_text(self):
                return '192.0.2.3'

        class NewValue(Ipv4Value):
            pass

        parse_uses_legacy = record_base._value_from_rdata_text_uses_legacy
        render_uses_legacy = record_base._value_to_rdata_text_uses_legacy
        parse_uses_legacy.cache_clear()
        render_uses_legacy.cache_clear()
        try:
            self.assertIs(
                record_base.value_from_rdata_text, value_from_rdata_text
            )
            self.assertIs(record_base.value_to_rdata_text, value_to_rdata_text)
            with patch.object(
                record_base, '_mro_owner', wraps=record_base._mro_owner
            ) as mro_owner:
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    for _ in range(2):
                        self.assertEqual(
                            '192.0.2.2',
                            record_base.value_from_rdata_text(
                                LegacyValue, '192.0.2.1'
                            ),
                        )
                        self.assertEqual(
                            '192.0.2.3',
                            record_base.value_to_rdata_text(
                                LegacyValue('192.0.2.1')
                            ),
                        )

                self.assertEqual(4, mro_owner.call_count)
                self.assertEqual(
                    [
                        '`LegacyValue.parse_rdata_text` is DEPRECATED. '
                        'Implement `from_rdata_text()` instead. Will be '
                        'removed in 2.0.',
                        '`LegacyValue.rdata_text` is DEPRECATED. Implement '
                        '`to_rdata_text()` instead. Will be removed in 2.0.',
                    ]
                    * 2,
                    [str(warning.message) for warning in caught],
                )

                self.assertEqual(
                    '192.0.2.1',
                    record_base.value_from_rdata_text(NewValue, '192.0.2.1'),
                )
                self.assertEqual(
                    '192.0.2.1',
                    record_base.value_to_rdata_text(NewValue('192.0.2.1')),
                )
                self.assertEqual(8, mro_owner.call_count)
        finally:
            parse_uses_legacy.cache_clear()
            render_uses_legacy.cache_clear()

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

        self.assertNotIn('AA', Record.registered_types())

        Record.register_type(AaRecord)
        aa = Record.new(
            self.zone,
            'registered',
            {'ttl': 360, 'type': 'AA', 'value': 'does.not.matter.'},
        )
        self.assertEqual(AaRecord, aa.__class__)

        self.assertIn('AA', Record.registered_types())

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

        # The record-class compatibility helpers remain available and
        # Record.from_rrs uses them directly.
        self.assertEqual(
            {'ttl': 42, 'type': 'A', 'values': ['1.2.3.4', '2.3.4.5']},
            ARecord.data_from_rrs((rrs[0], rrs[3])),
        )
        self.assertEqual(
            {'ttl': 46, 'type': 'CNAME', 'value': 'target.unit.tests.'},
            CnameRecord.data_from_rrs((rrs[4],)),
        )

    def test_rrset_conversion(self):
        zone = Zone('unit.tests.', [])
        source = object()
        rrsets = (
            Rrset('www.unit.tests.', 'AAAA', 45, ['fc00::3']),
            Rrset('unit.tests.', 'A', 42, ['2.3.4.5', '1.2.3.4', '1.2.3.4']),
            Rrset('www.unit.tests.', 'A', 44, ['3.4.5.6']),
        )

        records = Record.from_rrsets(zone, rrsets, source=source)
        self.assertEqual(
            [('', 'A'), ('www', 'A'), ('www', 'AAAA')],
            [(record.name, record._type) for record in records],
        )
        self.assertEqual(['1.2.3.4', '1.2.3.4', '2.3.4.5'], records[0].values)
        self.assertTrue(all(record.source is source for record in records))

        rrset = records[0].to_rrset()
        self.assertEqual('unit.tests.', rrset.name)
        self.assertEqual('A', rrset._type)
        self.assertEqual(42, rrset.ttl)
        self.assertEqual(['1.2.3.4', '1.2.3.4', '2.3.4.5'], rrset.rdatas)
        self.assertEqual(records[0].data, Record.from_rrset(zone, rrset).data)

        self.assertEqual([], Record.from_rrsets(zone, []))

        with self.assertRaises(RecordException) as ctx:
            Rrset('unit.tests.', 'A', 42, [])
        self.assertEqual(
            'Invalid Rrset unit.tests. A: at least one RDATA value is required',
            str(ctx.exception),
        )

        class EmptyRrset:
            name = 'unit.tests.'
            _type = 'A'
            rdatas = []

        with self.assertRaises(RecordException) as ctx:
            Record.from_rrset(zone, EmptyRrset())
        self.assertEqual(
            'Invalid Rrset unit.tests. A: at least one RDATA value is required',
            str(ctx.exception),
        )
        with self.assertRaises(RecordException) as ctx:
            Record.from_rrsets(
                zone,
                (
                    Rrset('unit.tests.', 'A', 42, ['1.2.3.4']),
                    Rrset('unit.tests.', 'A', 43, ['2.3.4.5']),
                ),
            )
        self.assertEqual('Duplicate Rrset unit.tests. A', str(ctx.exception))

        cname = Rrset(
            'cname.unit.tests.',
            'CNAME',
            42,
            ['one.unit.tests.', 'two.unit.tests.'],
        )
        expected = (
            'Invalid Rrset cname.unit.tests. CNAME: exactly one RDATA value '
            'is required for a single-value record'
        )
        with self.assertRaises(RecordException) as ctx:
            Record.from_rrset(zone, cname)
        self.assertEqual(expected, str(ctx.exception))
        with self.assertRaises(RecordException) as ctx:
            Record.from_rrsets(zone, [cname])
        self.assertEqual(expected, str(ctx.exception))

        unknown = Rrset('unknown.unit.tests.', 'UNKNOWN', 42, ['value'])
        for convert in (
            lambda: Record.from_rrset(zone, unknown),
            lambda: Record.from_rrsets(zone, [unknown]),
        ):
            with self.assertRaises(RecordException) as ctx:
                convert()
            self.assertEqual(
                'Unknown record type: "UNKNOWN"', str(ctx.exception)
            )

    def test_rrset_lenient_and_legacy_conversion(self):
        zone = Zone('unit.tests.', [])
        source = object()
        rrset = Rrset('bad.unit.tests.', 'CNAME', 42, ['not a valid target'])
        record = Record.from_rrset(zone, rrset, lenient=True, source=source)
        self.assertEqual('not a valid target', record.value)
        self.assertIs(source, record.source)

        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            legacy = [
                Rr('unit.tests.', 'A', 42, '2.3.4.5'),
                Rr('unit.tests.', 'A', 99, '1.2.3.4'),
            ]
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            records = Record.from_rrs(
                zone, iter(legacy), lenient=True, source=source
            )
        self.assertEqual(
            [
                '`Record.from_rrs` is DEPRECATED. Use '
                '`Record.from_rrsets()` instead. Will be removed in 2.0.'
            ],
            [
                str(warning.message)
                for warning in caught
                if 'Record.from_rrs' in str(warning.message)
            ],
        )
        self.assertEqual(42, records[0].ttl)
        self.assertEqual(['1.2.3.4', '2.3.4.5'], records[0].values)
        self.assertIs(source, records[0].source)

        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            legacy = [
                Rr('cname.unit.tests.', 'CNAME', 42, 'one.unit.tests.'),
                Rr('cname.unit.tests.', 'CNAME', 99, 'two.unit.tests.'),
            ]
            records = Record.from_rrs(zone, legacy, source=source)
        self.assertEqual(1, len(records))
        self.assertEqual(42, records[0].ttl)
        self.assertEqual('one.unit.tests.', records[0].value)
        self.assertIs(source, records[0].source)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            self.assertEqual([], Record.from_rrs(zone, ()))
        self.assertEqual(
            '`Record.from_rrs` is DEPRECATED. Use `Record.from_rrsets()` '
            'instead. Will be removed in 2.0.',
            str(caught[0].message),
        )

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
        self.assertIn('missing type', str(ctx.exception))

        # Unknown type
        with self.assertRaises(Exception) as ctx:
            Record.new(self.zone, 'unknown', {'type': 'XXX'})
        self.assertIn('Unknown record type', str(ctx.exception))

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
        self.assertIs(RdataParseError, RrParseError)
        self.assertEqual(
            'failed to parse string value as RDATA presentation text',
            str(RdataParseError()),
        )
        self.assertEqual(
            'failed to parse string value as RDATA presentation text',
            str(RrParseError()),
        )
        self.assertEqual(
            'custom message', str(RdataParseError('custom message'))
        )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            expected_line = currentframe().f_lineno + 1
            rr = Rr('name', 'type', 42, 'Hello World!')
        self.assertEqual(
            '`Rr` is DEPRECATED. Use `Rrset` instead. Will be removed in 2.0.',
            str(caught[0].message),
        )
        self.assertEqual(__file__, caught[0].filename)
        self.assertEqual(expected_line, caught[0].lineno)
        self.assertEqual('name', rr.name)
        self.assertEqual('type', rr._type)
        self.assertEqual(42, rr.ttl)
        self.assertEqual('Hello World!', rr.rdata)
        self.assertEqual('Rr<name, type, 42, Hello World!', rr.__repr__())

        rrset = Rrset('name', 'type', 42, iter(('one', 'two')))
        self.assertEqual('name', rrset.name)
        self.assertEqual('type', rrset._type)
        self.assertEqual(42, rrset.ttl)
        self.assertEqual(['one', 'two'], rrset.rdatas)
        self.assertEqual(
            "Rrset<name, type, 42, ['one', 'two']>", rrset.__repr__()
        )

        same = Rrset('name', 'type', 42, ('one', 'two'))
        later = Rrset('name', 'type', 43, ('one', 'two'))
        self.assertEqual(rrset, same)
        self.assertNotEqual(rrset, later)
        self.assertEqual([rrset, later], sorted((later, rrset)))
        same.rdatas.append('three')
        self.assertNotEqual(rrset, same)

        invalid_rdatas = (
            ('value', 'RDATA values must be a non-string iterable of strings'),
            (None, 'RDATA values must be a non-string iterable of strings'),
            (['value', 42], 'RDATA value at index 1 must be a string'),
        )
        for rdatas, message in invalid_rdatas:
            with self.subTest(rdatas=rdatas):
                with self.assertRaises(RecordException) as ctx:
                    Rrset('name', 'type', 42, rdatas)
                self.assertEqual(
                    f'Invalid Rrset name type: {message}', str(ctx.exception)
                )

        zone = Zone('unit.tests.', [])
        record = Record.new(
            zone,
            'a',
            {'ttl': 42, 'type': 'A', 'values': ['1.2.3.4', '2.3.4.5']},
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            self.assertEqual(
                ('a.unit.tests.', 42, 'A', ['1.2.3.4', '2.3.4.5']), record.rrs
            )
        self.assertEqual(
            '`Record.rrs` is DEPRECATED. Use `Record.to_rrset()` instead. '
            'Will be removed in 2.0.',
            str(caught[0].message),
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

    def test_rrs_round_trip_all_core_types(self):
        values = {
            'A': '192.0.2.1',
            'AAAA': '2001:db8::1',
            'ALIAS': 'target.unit.tests.',
            'CAA': {'flags': 0, 'tag': 'issue', 'value': 'ca.example'},
            'CNAME': 'target.unit.tests.',
            'DNAME': 'target.unit.tests.',
            'DS': {
                'key_tag': 1,
                'algorithm': 2,
                'digest_type': 3,
                'digest': 'ABCD',
            },
            'HTTPS': {
                'svcpriority': 1,
                'targetname': 'target.unit.tests.',
                'svcparams': {'port': 443},
            },
            'LOC': {
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
            },
            'MX': {'preference': 10, 'exchange': 'mx.unit.tests.'},
            'NAPTR': {
                'order': 1,
                'preference': 2,
                'flags': 'U',
                'service': 'E2U+sip',
                'regexp': '!^.*$!sip:info@example.com!',
                'replacement': '.',
            },
            'NS': 'ns.unit.tests.',
            'OPENPGPKEY': 'abc123',
            'PTR': 'target.unit.tests.',
            'SPF': 'v=spf1 \\;all',
            'SRV': {
                'priority': 1,
                'weight': 2,
                'port': 443,
                'target': 'target.unit.tests.',
            },
            'SSHFP': {
                'algorithm': 1,
                'fingerprint_type': 2,
                'fingerprint': 'A' * 64,
            },
            'SVCB': {
                'svcpriority': 1,
                'targetname': 'target.unit.tests.',
                'svcparams': {'port': 443},
            },
            'TLSA': {
                'certificate_usage': 1,
                'selector': 1,
                'matching_type': 1,
                'certificate_association_data': 'ABCD',
            },
            'TXT': 'value \\;with semicolon',
            'URI': {
                'priority': 1,
                'weight': 2,
                'target': 'https://target.unit.tests/',
            },
            'URLFWD': {
                'path': '/',
                'target': 'https://target.unit.tests/',
                'code': 301,
                'masking': 0,
                'query': 0,
            },
        }
        second_values = {
            'A': '192.0.2.2',
            'AAAA': '2001:db8::2',
            'CAA': {'flags': 0, 'tag': 'iodef', 'value': 'other.example'},
            'DS': {
                'key_tag': 2,
                'algorithm': 2,
                'digest_type': 3,
                'digest': 'EF01',
            },
            'HTTPS': {
                'svcpriority': 2,
                'targetname': 'other.unit.tests.',
                'svcparams': {'port': 8443},
            },
            'LOC': {
                'lat_degrees': 31,
                'lat_minutes': 58,
                'lat_seconds': 53.1,
                'lat_direction': 'S',
                'long_degrees': 115,
                'long_minutes': 49,
                'long_seconds': 11.7,
                'long_direction': 'E',
                'altitude': 20,
                'size': 10,
                'precision_horz': 10,
                'precision_vert': 2,
            },
            'MX': {'preference': 20, 'exchange': 'mx2.unit.tests.'},
            'NAPTR': {
                'order': 2,
                'preference': 2,
                'flags': 'U',
                'service': 'E2U+sip',
                'regexp': '!^.*$!sip:other@example.com!',
                'replacement': '.',
            },
            'NS': 'ns2.unit.tests.',
            'OPENPGPKEY': 'def456',
            'PTR': 'other.unit.tests.',
            'SPF': 'v=spf1 include:other.unit.tests. \\;all',
            'SRV': {
                'priority': 2,
                'weight': 2,
                'port': 443,
                'target': 'other.unit.tests.',
            },
            'SSHFP': {
                'algorithm': 2,
                'fingerprint_type': 2,
                'fingerprint': 'B' * 64,
            },
            'SVCB': {
                'svcpriority': 2,
                'targetname': 'other.unit.tests.',
                'svcparams': {'port': 8443},
            },
            'TLSA': {
                'certificate_usage': 2,
                'selector': 1,
                'matching_type': 1,
                'certificate_association_data': 'EF01',
            },
            'TXT': 'another \\;value',
            'URI': {
                'priority': 2,
                'weight': 2,
                'target': 'https://other.unit.tests/',
            },
            'URLFWD': {
                'path': '/other',
                'target': 'https://other.unit.tests/',
                'code': 302,
                'masking': 0,
                'query': 0,
            },
        }
        names = {'ALIAS': '', 'SRV': '_srv._tcp', 'URI': '_uri._tcp'}
        for _type, value in values.items():
            data = {'ttl': 30, 'type': _type}
            if _type in second_values:
                data['values'] = [value, second_values[_type]]
            else:
                data['value'] = value
            record = Record.new(
                self.zone, names.get(_type, _type.lower()), data
            )
            if _type in second_values:
                self.assertEqual(2, len(record.values), _type)
                self.assertNotEqual(record.values[0], record.values[1], _type)
            value_type = record._value_type
            value_obj = (
                record.values[0] if hasattr(record, 'values') else record.value
            )
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                if _type in ('SPF', 'TXT'):
                    self.assertEqual(value_obj, value_obj.rdata_text)
                    self.assertEqual(
                        value_obj.replace(';', '\\;'),
                        value_type.parse_rdata_text(value_obj),
                    )
                else:
                    rdata = value_obj.to_rdata_text()
                    self.assertEqual(rdata, value_obj.rdata_text)
                    self.assertEqual(
                        value_type.from_rdata_text(rdata),
                        value_type.parse_rdata_text(rdata),
                    )
            value_type_name = value_type.__name__
            if _type in ('SPF', 'TXT'):
                replacements = (
                    'str(value)',
                    f'{value_type_name}.normalize_raw_text()',
                )
            else:
                replacements = (
                    f'{value_type_name}.to_rdata_text()',
                    f'{value_type_name}.from_rdata_text()',
                )
            self.assertEqual(
                [
                    f'`{value_type_name}.rdata_text` is DEPRECATED. Use '
                    f'`{replacements[0]}` instead. Will be removed in 2.0.',
                    f'`{value_type_name}.parse_rdata_text` is DEPRECATED. Use '
                    f'`{replacements[1]}` instead. Will be removed in 2.0.',
                ],
                [str(warning.message) for warning in caught],
                _type,
            )
            rrset = record.to_rrset()
            round_trip = Record.from_rrset(self.zone, rrset)
            self.assertEqual(record.data, round_trip.data, _type)

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
        name = name[:-1]
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

        # double dots are not valid, ends with
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'this.ends.with.a.dot.',
                {'ttl': 301, 'type': 'A', 'value': '1.2.3.4'},
            )
        reason = ctx.exception.reasons[0]
        self.assertEqual(
            'invalid name, double `.` in "this.ends.with.a.dot..unit.tests."',
            reason,
        )

        # double dots are not valid when eplxicit
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'this.has.double..dots',
                {'ttl': 301, 'type': 'A', 'value': '1.2.3.4'},
            )
        reason = ctx.exception.reasons[0]
        self.assertEqual(
            'invalid name, double `.` in "this.has.double..dots.unit.tests."',
            reason,
        )

        # double dots in idna names
        with self.assertRaises(ValidationError) as ctx:
            Record.new(
                self.zone,
                'niño.',
                {'ttl': 301, 'type': 'A', 'value': '1.2.3.4'},
            )
        reason = ctx.exception.reasons[0]
        self.assertEqual(
            'invalid name, double `.` in "niño..unit.tests."', reason
        )

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
        self.assertNotIn(', line', str(ctx.exception))

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
        self.assertIn('needle', str(ctx.exception))

    def test_invalid_type_context(self):
        # fails validation, no context
        with self.assertRaises(Exception) as ctx:
            Record.new(
                self.zone, 'www', {'type': 'X', 'ttl': 42, 'value': '1.2.3.4'}
            )
        self.assertNotIn(', line', str(ctx.exception))

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
        self.assertIn('needle', str(ctx.exception))

    def test_missing_type_context(self):
        # fails validation, no context
        with self.assertRaises(Exception) as ctx:
            Record.new(self.zone, 'www', {'ttl': 42, 'value': '1.2.3.4'})
        self.assertNotIn(', line', str(ctx.exception))

        # fails validation, with context
        with self.assertRaises(Exception) as ctx:
            Record.new(
                self.zone,
                'www',
                ContextDict({'ttl': 42, 'value': '1.2.3.4'}, context='needle'),
            )
        self.assertIn('needle', str(ctx.exception))

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
            attr = 'parse_rdata_texts'
            method = getattr(cls, attr)
            self.assertTrue(method, f'{_type}, {cls} has {attr}')
            self.assertTrue(
                callable(method), f'{_type}, {cls} {attr} is callable'
            )

            value_type = getattr(cls, '_value_type')
            self.assertTrue(value_type, f'{_type}, {cls} has _value_type')

            if not value_type.__module__.startswith('octodns.'):
                continue

            attr = 'from_rdata_text'
            method = getattr(value_type, attr)
            self.assertTrue(method, f'{_type}, {cls} has {attr}')
            self.assertTrue(
                callable(method), f'{_type}, {cls} {attr} is callable'
            )

            attr = 'to_rdata_text'
            method = getattr(value_type, attr)
            self.assertTrue(method, f'{_type}, {cls} has {attr}')
            self.assertTrue(
                callable(method), f'{_type}, {cls} {attr} is callable'
            )

            attr = 'parse_rdata_text'
            method = getattr(value_type, attr)
            self.assertTrue(method, f'{_type}, {cls} has {attr}')
            self.assertTrue(
                callable(method), f'{_type}, {cls} {attr} is callable'
            )

            attr = 'rdata_text'
            method = getattr(value_type, attr)
            self.assertTrue(method, f'{_type}, {cls} has {attr}')
            # this one is a @property so not callable


class TestValidators(TestCase):
    def test_legacy_record_validate_deprecation(self):
        # 3rd-party records that still override Record.validate get a
        # DeprecationWarning at class-definition time, telling them to
        # migrate to declaring VALIDATORS before 2.0.
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')

            class LegacyRecord(ARecord):
                @classmethod
                def validate(cls, name, fqdn, data):
                    return []

        matched = [
            w
            for w in caught
            if issubclass(w.category, DeprecationWarning)
            and 'LegacyRecord.validate' in str(w.message)
        ]
        self.assertTrue(matched)

    def test_legacy_record_validate_new_still_works(self):
        # A 3rd-party Record subclass whose overridden `validate` classmethod
        # predates the `disabled` param must still be usable via Record.new
        # (falls back to calling it without `disabled`, with a deprecation
        # warning) rather than raising a TypeError.
        with warnings.catch_warnings(record=True):
            warnings.simplefilter('ignore')

            class LegacyValidateRecord(ValuesMixin, Record):
                _type = 'LEGACY-VALIDATE-TEST'
                _value_type = NsValue

                @classmethod
                def validate(cls, name, fqdn, data):
                    return []

        Record.register_type(LegacyValidateRecord)

        zone = Zone('unit.tests.', [])
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            record = Record.new(
                zone,
                'www',
                {
                    'type': 'LEGACY-VALIDATE-TEST',
                    'ttl': 300,
                    'value': 'does.not.matter.',
                },
            )
        self.assertEqual('www', record.name)
        matched = [
            w
            for w in caught
            if issubclass(w.category, DeprecationWarning)
            and 'disabled' in str(w.message)
            and 'LegacyValidateRecord' in str(w.message)
        ]
        self.assertTrue(matched)

    def test_record_new_reraises_unrelated_typeerror(self):
        # A TypeError raised by validate() for a reason unrelated to the
        # `disabled` param must propagate rather than being misidentified
        # as an old-signature validator and silently retried.
        with warnings.catch_warnings(record=True):
            warnings.simplefilter('ignore')

            class BuggyValidateRecord(ValuesMixin, Record):
                _type = 'BUGGY-VALIDATE-TEST'
                _value_type = NsValue

                @classmethod
                def validate(cls, name, fqdn, data, disabled=None):
                    return 'not-a-list' + 5

        Record.register_type(BuggyValidateRecord)

        zone = Zone('unit.tests.', [])
        with self.assertRaises(TypeError):
            Record.new(
                zone,
                'www',
                {
                    'type': 'BUGGY-VALIDATE-TEST',
                    'ttl': 300,
                    'value': 'does.not.matter.',
                },
            )
