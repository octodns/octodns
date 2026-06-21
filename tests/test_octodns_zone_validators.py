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
