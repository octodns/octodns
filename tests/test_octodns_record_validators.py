#
#
#

import warnings
from unittest import TestCase

from octodns.record import (
    AliasRecord,
    ARecord,
    CnameRecord,
    MxRecord,
    Record,
    RecordException,
)
from octodns.record.alias import AliasRootValidator
from octodns.record.base import (
    HealthcheckValidator,
    NameValidator,
    TtlValidator,
)
from octodns.record.cname import CnameRootValidator
from octodns.record.dynamic import DynamicValidator
from octodns.record.geo import GeoValidator
from octodns.record.srv import SrvNameValidator, SrvRecord
from octodns.record.uri import UriNameValidator, UriRecord
from octodns.record.validator import (
    RecordValidator,
    ValidatorRegistry,
    ValueValidator,
)


class TestValidatorBase(TestCase):
    def test_record_validator_base(self):
        self.assertEqual(
            [], RecordValidator('test').validate(ARecord, '', 'unit.tests.', {})
        )

    def test_value_validator_base(self):
        self.assertEqual([], ValueValidator('test').validate(None, None, 'A'))

    def test_validator_requires_id(self):
        with self.assertRaises(ValueError):
            RecordValidator('')
        with self.assertRaises(ValueError):
            RecordValidator(None)
        with self.assertRaises(TypeError):
            RecordValidator()
        with self.assertRaises(ValueError):
            ValueValidator('')
        with self.assertRaises(ValueError):
            ValueValidator(None)
        with self.assertRaises(TypeError):
            ValueValidator()
        # Concrete subclasses inherit the same requirement.
        with self.assertRaises(ValueError):
            NameValidator('')
        with self.assertRaises(ValueError):
            NameValidator(None)
        # A provided id is stored on the instance.
        self.assertEqual('custom', NameValidator('custom').id)

    def test_validator_sets_attribute(self):
        # Default sets value is None — always active regardless of enabled sets.
        v = RecordValidator('test-default-sets')
        self.assertIsNone(v.sets)

        # Can be overridden with any iterable.
        v2 = RecordValidator('test-custom-sets', sets=('rfc', 'best-practice'))
        self.assertEqual({'rfc', 'best-practice'}, v2.sets)

        # Empty sets is valid (never activated via set membership).
        v3 = RecordValidator('test-empty-sets', sets=())
        self.assertEqual(set(), v3.sets)

        # Same applies to ValueValidator.
        vv = ValueValidator('test-value-sets')
        self.assertIsNone(vv.sets)


class TestBuiltinValidators(TestCase):
    def test_name_validator(self):
        self.assertEqual(
            [],
            NameValidator('name').validate(
                ARecord, 'www', 'www.unit.tests.', {}
            ),
        )
        self.assertEqual(
            ['invalid name "@", use "" instead'],
            NameValidator('name').validate(ARecord, '@', '@.unit.tests.', {}),
        )
        long_name = '.'.join(['a' * 60] * 5)
        long_fqdn = f'{long_name}.unit.tests.'
        reasons = NameValidator('name').validate(
            ARecord, long_name, long_fqdn, {}
        )
        self.assertTrue(
            any('too long at' in r and 'max is 253' in r for r in reasons)
        )
        long_label = 'x' * 64
        reasons = NameValidator('name').validate(
            ARecord, long_label, f'{long_label}.unit.tests.', {}
        )
        self.assertTrue(
            any('invalid label' in r and 'max is 63' in r for r in reasons)
        )
        self.assertEqual(
            ['invalid name, double `.` in "foo..bar.unit.tests."'],
            NameValidator('name').validate(
                ARecord, 'foo..bar', 'foo..bar.unit.tests.', {}
            ),
        )

    def test_ttl_validator(self):
        self.assertEqual(
            [],
            TtlValidator('ttl').validate(
                ARecord, '', 'unit.tests.', {'ttl': 42}
            ),
        )
        self.assertEqual(
            ['missing ttl'],
            TtlValidator('ttl').validate(ARecord, '', 'unit.tests.', {}),
        )
        self.assertEqual(
            ['invalid ttl'],
            TtlValidator('ttl').validate(
                ARecord, '', 'unit.tests.', {'ttl': -1}
            ),
        )

    def test_healthcheck_validator(self):
        self.assertEqual(
            [],
            HealthcheckValidator('healthcheck').validate(
                ARecord, '', 'unit.tests.', {}
            ),
        )
        self.assertEqual(
            [],
            HealthcheckValidator('healthcheck').validate(
                ARecord,
                '',
                'unit.tests.',
                {'octodns': {'healthcheck': {'protocol': 'HTTPS'}}},
            ),
        )
        self.assertEqual(
            ['invalid healthcheck protocol'],
            HealthcheckValidator('healthcheck').validate(
                ARecord,
                '',
                'unit.tests.',
                {'octodns': {'healthcheck': {'protocol': 'BOGUS'}}},
            ),
        )

    def test_dynamic_validator(self):
        # no `dynamic` key -> no reasons
        self.assertEqual(
            [],
            DynamicValidator('dynamic').validate(
                ARecord, '', 'unit.tests.', {}
            ),
        )
        # `dynamic` and `geo` co-present triggers a reason
        reasons = DynamicValidator('dynamic').validate(
            ARecord, '', 'unit.tests.', {'dynamic': {}, 'geo': {}}
        )
        self.assertIn('"dynamic" record with "geo" content', reasons)

    def test_geo_validator(self):
        # no `geo` key -> no reasons
        self.assertEqual(
            [], GeoValidator('geo').validate(ARecord, '', 'unit.tests.', {})
        )
        # invalid geo code surfaces a reason
        reasons = GeoValidator('geo').validate(
            ARecord, '', 'unit.tests.', {'geo': {'X': ['1.2.3.4']}}
        )
        self.assertIn('invalid geo "X"', reasons)

    def test_srv_name_validator(self):
        self.assertEqual(
            [],
            SrvNameValidator('srv-name').validate(
                SrvRecord, '_sip._tcp', '_sip._tcp.unit.tests.', {}
            ),
        )
        self.assertEqual(
            ['invalid name for SRV record'],
            SrvNameValidator('srv-name').validate(
                SrvRecord, 'bad', 'bad.unit.tests.', {}
            ),
        )

    def test_cname_root_validator(self):
        self.assertEqual(
            [],
            CnameRootValidator('cname-root').validate(
                CnameRecord, 'www', 'www.unit.tests.', {}
            ),
        )
        self.assertEqual(
            ['root CNAME not allowed'],
            CnameRootValidator('cname-root').validate(
                CnameRecord, '', 'unit.tests.', {}
            ),
        )

    def test_alias_root_validator(self):
        self.assertEqual(
            [],
            AliasRootValidator('alias-root').validate(
                AliasRecord, '', 'unit.tests.', {}
            ),
        )
        self.assertEqual(
            ['non-root ALIAS not allowed'],
            AliasRootValidator('alias-root').validate(
                AliasRecord, 'www', 'www.unit.tests.', {}
            ),
        )

    def test_uri_name_validator(self):
        self.assertEqual(
            [],
            UriNameValidator('uri-name').validate(
                UriRecord, '_sip._tcp', '_sip._tcp.unit.tests.', {}
            ),
        )
        self.assertEqual(
            ['invalid name for URI record'],
            UriNameValidator('uri-name').validate(
                UriRecord, 'bad', 'bad.unit.tests.', {}
            ),
        )


class TestValidatorRegistry(TestCase):
    def test_register(self):
        reg = ValidatorRegistry()
        v_record = RecordValidator('reg-record')
        v_value = ValueValidator('reg-value')
        reg.register(v_record, types=['A'])
        reg.register(v_value, types=['A'])
        avail = reg.available()
        self.assertIn(v_record, avail['record'].get('A', []))
        self.assertIn(v_value, avail['value'].get('A', []))

    def test_register_errors(self):
        reg = ValidatorRegistry()

        # Must be a RecordValidator or ValueValidator instance.
        with self.assertRaises(RecordException) as ctx:
            reg.register(object())
        self.assertIn(
            'must be a RecordValidator or ValueValidator', str(ctx.exception)
        )

        # Duplicate id within the same bucket is rejected.
        v = RecordValidator('dup-test')
        reg.register(v, types=['A'])
        with self.assertRaises(RecordException) as ctx:
            reg.register(v, types=['A'])
        self.assertIn('"dup-test" already registered', str(ctx.exception))

    def test_register_replace(self):
        reg = ValidatorRegistry()
        original = RecordValidator('replace-test')
        reg.register(original, types=['A'])

        # Without replace=True, a duplicate id still raises.
        dupe = RecordValidator('replace-test')
        with self.assertRaises(RecordException) as ctx:
            reg.register(dupe, types=['A'])
        self.assertIn('"replace-test" already registered', str(ctx.exception))

        # With replace=True, the new instance overwrites the original.
        replacement = RecordValidator('replace-test')
        reg.register(replacement, types=['A'], replace=True)
        avail = reg.available_record['A']
        self.assertIs(replacement, avail['replace-test'])
        self.assertIsNot(original, avail['replace-test'])

        # Only the targeted type's bucket is affected — registering under a
        # different type with the same id does not touch the first bucket.
        other_type = RecordValidator('replace-test')
        reg.register(other_type, types=['AAAA'], replace=True)
        self.assertIs(replacement, reg.available_record['A']['replace-test'])
        self.assertIs(other_type, reg.available_record['AAAA']['replace-test'])

    def test_enable_sets(self):
        v_legacy = RecordValidator('ev-legacy', sets={'legacy'})
        v_rfc = RecordValidator('ev-rfc', sets={'rfc'})
        reg = ValidatorRegistry()
        reg.register(v_legacy, types=['A'])
        reg.register(v_rfc, types=['A'])

        # Nothing active for A yet.
        a_active = reg.registered()['record'].get('A', [])
        self.assertFalse(any(v.id == 'ev-legacy' for v in a_active))
        self.assertFalse(any(v.id == 'ev-rfc' for v in a_active))

        # Enabling one set activates only matching validators.
        reg.enable_sets(('legacy',))
        a_active = reg.registered()['record'].get('A', [])
        self.assertTrue(any(v.id == 'ev-legacy' for v in a_active))
        self.assertFalse(any(v.id == 'ev-rfc' for v in a_active))

        # Enabling a different set resets — previous set is no longer active.
        reg.enable_sets(('rfc',))
        a_active = reg.registered()['record'].get('A', [])
        self.assertFalse(any(v.id == 'ev-legacy' for v in a_active))
        self.assertTrue(any(v.id == 'ev-rfc' for v in a_active))

        # Enabling multiple sets activates all matching validators.
        reg.enable_sets(('legacy', 'rfc'))
        a_active = reg.registered()['record'].get('A', [])
        self.assertTrue(any(v.id == 'ev-legacy' for v in a_active))
        self.assertTrue(any(v.id == 'ev-rfc' for v in a_active))

        # Empty set activates only validators with sets=None.
        v_always = RecordValidator('ev-always')
        v_set = RecordValidator('ev-with-set', sets={'legacy'})
        reg2 = ValidatorRegistry()
        reg2.register(v_always)
        reg2.register(v_set)
        reg2.enable_sets(())
        all_active = [
            v for bucket in reg2.active_record.values() for v in bucket.values()
        ]
        self.assertIn(v_always, all_active)
        self.assertNotIn(v_set, all_active)

    def test_enable(self):
        v = RecordValidator('ev-single', sets={'rfc'})
        reg = ValidatorRegistry()
        reg.register(v, types=['MX'])
        reg.enable_sets([])

        # Not yet active after enable_sets([]).
        mx_active = reg.registered()['record'].get('MX', [])
        self.assertFalse(any(v.id == 'ev-single' for v in mx_active))

        # Activate for a specific type.
        reg.enable('ev-single', types=['MX'])
        mx_active = reg.registered()['record'].get('MX', [])
        self.assertTrue(any(v.id == 'ev-single' for v in mx_active))

        # Unknown id raises RecordException.
        with self.assertRaises(RecordException) as ctx:
            reg.enable('does-not-exist')
        self.assertIn('Unknown validator id', str(ctx.exception))

    def test_disable(self):
        reg = ValidatorRegistry()

        # Bridge (_-prefixed) validators cannot be disabled.
        with self.assertRaises(RecordException) as ctx:
            reg.disable('_values-type')
        self.assertIn('Cannot disable bridge validator', str(ctx.exception))

        # Disabling by types= removes only from those active buckets.
        v = RecordValidator('my-test')
        reg.register(v, types=['A', 'AAAA'])
        reg.enable('my-test', types=['A', 'AAAA'])
        reg.disable('my-test', types=['A'])
        registry = reg.registered()['record']
        self.assertNotIn(v, registry.get('A', []))
        self.assertIn(v, registry.get('AAAA', []))

        # Disabling without types removes from every active bucket.
        v2 = RecordValidator('my-test2')
        reg2 = ValidatorRegistry()
        reg2.register(v2, types=['A', 'AAAA'])
        reg2.enable('my-test2', types=['A', 'AAAA'])
        reg2.disable('my-test2')
        registry2 = reg2.registered()['record']
        self.assertNotIn(v2, registry2.get('A', []))
        self.assertNotIn(v2, registry2.get('AAAA', []))

        # Disabling from a type with no active bucket is a no-op.
        reg3 = ValidatorRegistry()
        self.assertEqual(0, reg3.disable('nonexistent-id', types=['FAKETYPE']))

        # Return value counts how many active buckets the id was removed from.
        v3 = RecordValidator('counted-test')
        reg4 = ValidatorRegistry()
        reg4.register(v3, types=['A', 'AAAA'])
        reg4.enable('counted-test', types=['A', 'AAAA'])
        self.assertEqual(1, reg4.disable('counted-test', types=['A']))
        self.assertEqual(1, reg4.disable('counted-test', types=['AAAA']))
        self.assertEqual(0, reg4.disable('counted-test', types=['A', 'AAAA']))

        # Without types= it counts every active bucket.
        v4 = RecordValidator('counted-global')
        reg5 = ValidatorRegistry()
        reg5.register(v4, types=['A', 'AAAA', 'TXT'])
        reg5.enable('counted-global', types=['A', 'AAAA', 'TXT'])
        self.assertEqual(3, reg5.disable('counted-global'))
        self.assertEqual(0, reg5.disable('counted-global'))

    def test_available(self):
        v = RecordValidator('avail-test', sets={'rfc'})
        reg = ValidatorRegistry()
        reg.register(v, types=['TXT'])
        avail = reg.available()
        self.assertIn(v, avail['record'].get('TXT', []))
        # Not in active registry until explicitly enabled.
        active = reg.registered()
        self.assertNotIn(v, active['record'].get('TXT', []))

    def test_process_record(self):
        class ForbidBadPrefix(RecordValidator):
            def __init__(self, prefix):
                super().__init__(id='test-forbid-bad-prefix')
                self.prefix = prefix

            def validate(self, record_cls, name, fqdn, data):
                if name.startswith(self.prefix):
                    return [f'name starts with "{self.prefix}"']
                return []

        reg = ValidatorRegistry()
        reg.register(ForbidBadPrefix('bad-'), types=['A'])
        reg.enable('test-forbid-bad-prefix', types=['A'])
        self.assertIn(
            'name starts with "bad-"',
            reg.process_record(
                ARecord, 'bad-name', 'bad-name.unit.tests.', {'ttl': 30}
            ),
        )
        self.assertEqual(
            [], reg.process_record(ARecord, 'ok', 'ok.unit.tests.', {'ttl': 30})
        )

    def test_process_record_lazy_init(self):
        reg = ValidatorRegistry()
        reg.register(NameValidator('name', sets={'legacy'}))
        reg.register(TtlValidator('ttl', sets={'legacy'}))

        # Not configured — first call auto-enables legacy with a warning.
        self.assertFalse(reg.configured)
        with self.assertLogs('Record', level='WARNING') as logs:
            reg.process_record(ARecord, 'foo', 'foo.unit.tests.', {'ttl': 300})
        self.assertTrue(
            any('automatically enabling legacy set' in m for m in logs.output)
        )
        self.assertTrue(reg.configured)
        active_ids = {
            v.id
            for bucket in reg.active_record.values()
            for v in bucket.values()
        }
        self.assertIn('name', active_ids)

        # Subsequent calls are silent.
        with self.assertNoLogs('Record', level='WARNING'):
            reg.process_record(ARecord, 'foo', 'foo.unit.tests.', {'ttl': 300})

    def test_process_values(self):
        class ForbidWord(ValueValidator):
            def __init__(self, word):
                super().__init__(id='test-forbid-word')
                self.word = word

            def validate(self, value_cls, data, _type):
                if not isinstance(data, (list, tuple)):
                    data = [data]
                if any(v == self.word for v in data):
                    return [f'forbidden value "{self.word}"']
                return []

        reg = ValidatorRegistry()
        reg.register(ForbidWord('blocked'), types=['TXT'])
        reg.enable('test-forbid-word', types=['TXT'])
        self.assertIn(
            'forbidden value "blocked"',
            reg.process_values(str, ['blocked'], 'TXT'),
        )
        self.assertEqual([], reg.process_values(str, ['allowed'], 'TXT'))

    def test_process_values_legacy_deprecation(self):
        class LegacyValueType(str):
            @classmethod
            def validate(cls, data, _type):
                return ['legacy reason']

        reg = ValidatorRegistry()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            reasons = reg.process_values(LegacyValueType, ['x'], 'TXT')
        self.assertEqual(['legacy reason'], reasons)
        matched = [
            w
            for w in caught
            if issubclass(w.category, DeprecationWarning)
            and 'LegacyValueType.validate' in str(w.message)
        ]
        self.assertTrue(matched)

    def test_process_record_disabled_skips_by_id(self):
        class Forbidden(RecordValidator):
            def validate(self, record_cls, name, fqdn, data, disabled=None):
                return ['forbidden']

        reg = ValidatorRegistry()
        reg.register(Forbidden('test-disableable'), types=['MX'])
        reg.enable('test-disableable', types=['MX'])

        # Not disabled: reason fires.
        self.assertEqual(
            ['forbidden'],
            reg.process_record(MxRecord, 'foo', 'foo.unit.tests.', {}),
        )
        # Disabled for this type: skipped.
        self.assertEqual(
            [],
            reg.process_record(
                MxRecord,
                'foo',
                'foo.unit.tests.',
                {},
                disabled={'MX': {'test-disableable'}},
            ),
        )
        # Disabled for a different type: still fires.
        self.assertEqual(
            ['forbidden'],
            reg.process_record(
                MxRecord,
                'foo',
                'foo.unit.tests.',
                {},
                disabled={'A': {'test-disableable'}},
            ),
        )

    def test_process_record_disabled_never_skips_bridge(self):
        class Bridge(RecordValidator):
            def __init__(self):
                super().__init__(id='_test-bridge')

            def validate(self, record_cls, name, fqdn, data, disabled=None):
                return ['bridge reason']

        reg = ValidatorRegistry()
        reg.register(Bridge(), types=['MX'])
        reg.enable('_test-bridge', types=['MX'])
        # Even explicitly listed, bridge (underscore) ids are never skipped.
        self.assertEqual(
            ['bridge reason'],
            reg.process_record(
                MxRecord,
                'foo',
                'foo.unit.tests.',
                {},
                disabled={'MX': {'_test-bridge'}},
            ),
        )

    def test_process_record_reraises_unrelated_typeerror(self):
        class Buggy(RecordValidator):
            def validate(self, record_cls, name, fqdn, data, disabled=None):
                # Deliberately trigger a TypeError unrelated to the
                # `disabled` param so process_record must re-raise it
                # rather than treat it as an old-signature validator.
                return 'not-a-list' + 5

        reg = ValidatorRegistry()
        reg.register(Buggy('test-buggy'), types=['MX'])
        reg.enable('test-buggy', types=['MX'])
        with self.assertRaises(TypeError):
            reg.process_record(MxRecord, 'foo', 'foo.unit.tests.', {})

    def test_process_values_disabled_skips_by_id(self):
        class ForbidWord(ValueValidator):
            def validate(self, value_cls, data, _type):
                return ['forbidden value']

        reg = ValidatorRegistry()
        reg.register(ForbidWord('test-disableable-value'), types=['TXT'])
        reg.enable('test-disableable-value', types=['TXT'])

        self.assertEqual(
            ['forbidden value'], reg.process_values(str, ['x'], 'TXT')
        )
        self.assertEqual(
            [],
            reg.process_values(
                str, ['x'], 'TXT', disabled={'TXT': {'test-disableable-value'}}
            ),
        )

    def test_process_values_disabled_never_skips_bridge(self):
        class Bridge(ValueValidator):
            def __init__(self):
                super().__init__(id='_test-bridge-value')

            def validate(self, value_cls, data, _type):
                return ['bridge value reason']

        reg = ValidatorRegistry()
        reg.register(Bridge(), types=['TXT'])
        reg.enable('_test-bridge-value', types=['TXT'])
        self.assertEqual(
            ['bridge value reason'],
            reg.process_values(
                str, ['x'], 'TXT', disabled={'TXT': {'_test-bridge-value'}}
            ),
        )

    def test_process_record_legacy_validator_deprecation(self):
        # A validator that predates the `disabled` param still works, via
        # the TypeError-detection fallback, but emits a deprecation warning.
        class Legacy(RecordValidator):
            def validate(self, record_cls, name, fqdn, data):
                return ['legacy reason']

        reg = ValidatorRegistry()
        reg.register(Legacy('test-legacy'), types=['MX'])
        reg.enable('test-legacy', types=['MX'])
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            reasons = reg.process_record(MxRecord, 'foo', 'foo.unit.tests.', {})
        self.assertEqual(['legacy reason'], reasons)
        matched = [
            w
            for w in caught
            if issubclass(w.category, DeprecationWarning)
            and 'Legacy' in str(w.message)
        ]
        self.assertTrue(matched)

    def test_builtin_validator_ids_are_nonempty_and_unique(self):
        # Every registered validator must have a non-empty id. Ids within
        # each registry bucket must be unique (enforced by register, but
        # verified here). Well-known ids must be present somewhere.
        registry = Record.available_validators()
        seen = set()
        for layer_name, layer in registry.items():
            for bucket_key, validators in layer.items():
                ids = []
                for v in validators:
                    self.assertTrue(
                        getattr(v, 'id', None),
                        f'{v.__class__.__name__} missing id',
                    )
                    ids.append(v.id)
                    seen.add(v.id)
                self.assertEqual(
                    len(ids),
                    len(set(ids)),
                    f'duplicate {layer_name} validator ids for "{bucket_key}": {ids}',
                )

        for expected in (
            'name-rfc',
            'ttl-rfc',
            'healthcheck',
            '_values-type',
            '_value-type',
            'cname-root-rfc',
            'alias-root',
            'mx-value',
            'ip-value-rfc',
            'target-value-rfc',
            'targets-value-rfc',
            'target-value-best-practice',
            'targets-value-best-practice',
        ):
            self.assertIn(expected, seen)
