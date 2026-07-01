#
#
#

from unittest import TestCase

from octodns.record import Record
from octodns.zone import Zone
from octodns.zone.exception import ValidationError, ZoneException
from octodns.zone.mail import MailZoneValidator
from octodns.zone.validator import (
    ValidationReason,
    ZoneValidator,
    ZoneValidatorRegistry,
)


def _make_zone(name='unit.tests.'):
    return Zone(name, [])


def _add_record(zone, name, data, lenient=True):
    if 'ttl' not in data:
        data['ttl'] = 300
    return Record.new(zone, name, data, lenient=lenient)


class TestValidationError(TestCase):
    def test_validation_error_context(self):
        v = ValidationReason('reason', [])
        err = ValidationError('unit.tests.', [v], context='ctx')
        self.assertIn('ctx', str(err))
        self.assertEqual('ctx', err.context)

        # test without context
        err2 = ValidationError('unit.tests.', [v])
        self.assertNotIn('ctx', str(err2))


class TestZoneValidatorBase(TestCase):
    def test_zone_validator_base(self):
        v = ZoneValidator('test')
        zone = _make_zone()
        self.assertEqual([], v.validate(zone))

    def test_validator_requires_id(self):
        with self.assertRaises(ValueError):
            ZoneValidator('')
        with self.assertRaises(ValueError):
            ZoneValidator(None)

    def test_validation_reason(self):
        r1 = _add_record(_make_zone(), 'r1', {'type': 'A', 'value': '1.2.3.4'})
        reason = ValidationReason('problem', [r1])
        self.assertEqual('problem', str(reason))
        self.assertEqual('problem', repr(reason))
        self.assertFalse(reason.lenient)

        r2 = _add_record(
            _make_zone(),
            'r2',
            {'type': 'A', 'value': '1.2.3.4', 'octodns': {'lenient': True}},
        )
        reason2 = ValidationReason('lenient problem', [r2])
        self.assertTrue(reason2.lenient)

    def test_registry(self):
        registry = ZoneValidatorRegistry()
        v = ZoneValidator('test')
        registry.register(v)

        with self.assertRaises(ZoneException) as ctx:
            registry.register('not-a-validator')
        self.assertIn(
            'str must be a ZoneValidator instance', str(ctx.exception)
        )

        with self.assertRaises(ZoneException) as ctx:
            registry.register(v)
        self.assertIn('already registered', str(ctx.exception))

        registry.enable('test')
        self.assertIn('test', registry.active)
        self.assertEqual([v], registry.available_validators())
        self.assertEqual([v], registry.registered())

        with self.assertRaises(ZoneException) as ctx:
            registry.enable('unknown')
        self.assertIn('Unknown zone validator id', str(ctx.exception))

        registry.reset_active()
        self.assertEqual([], registry.registered())

        # Test process_zone auto-enabling legacy
        registry.configured = False
        registry.register(MailZoneValidator('mail', sets={'legacy'}))
        zone = _make_zone()
        registry.process_zone(zone)
        self.assertTrue(registry.configured)
        self.assertIn('mail', registry.active)

        registry.disable('mail')
        self.assertNotIn('mail', registry.active)

        with self.assertRaises(ZoneException) as ctx:
            registry.disable('_internal')
        self.assertIn('Cannot disable bridge', str(ctx.exception))

    def test_registry_replace(self):
        registry = ZoneValidatorRegistry()
        original = ZoneValidator('replace-test')
        registry.register(original)

        # Without replace=True, a duplicate id still raises.
        dupe = ZoneValidator('replace-test')
        with self.assertRaises(ZoneException) as ctx:
            registry.register(dupe)
        self.assertIn('"replace-test" already registered', str(ctx.exception))

        # With replace=True, the new instance overwrites the original.
        replacement = ZoneValidator('replace-test')
        registry.register(replacement, replace=True)
        self.assertIs(replacement, registry.available['replace-test'])
        self.assertIsNot(original, registry.available['replace-test'])

    def test_process_zone_disabled_skips_by_id(self):
        class Flagged(ZoneValidator):
            def validate(self, zone):
                return [ValidationReason('flagged', [])]

        registry = ZoneValidatorRegistry()
        registry.register(Flagged('test-flagged'))
        registry.enable('test-flagged')

        # Not disabled: reason fires.
        zone = _make_zone()
        reasons = registry.process_zone(zone)
        self.assertEqual(['flagged'], [str(r) for r in reasons])

        # Disabled for this zone: skipped.
        disabled_zone = Zone(
            'unit.tests.',
            [],
            validators={'zone': {'disable_validators': ['test-flagged']}},
        )
        self.assertEqual([], registry.process_zone(disabled_zone))

    def test_process_zone_disabled_never_skips_bridge(self):
        class Bridge(ZoneValidator):
            def __init__(self):
                super().__init__(id='_test-bridge-zone')

            def validate(self, zone):
                return [ValidationReason('bridge', [])]

        registry = ZoneValidatorRegistry()
        registry.register(Bridge())
        registry.enable('_test-bridge-zone')

        # A bridge id can't even be listed via config (Zone.__init__ raises),
        # so simulate a zone whose disabled set somehow contains one anyway
        # and confirm process_zone's own guard still refuses to skip it.
        zone = _make_zone()
        zone.disabled_zone_validators = frozenset({'_test-bridge-zone'})
        reasons = registry.process_zone(zone)
        self.assertEqual(['bridge'], [str(r) for r in reasons])
