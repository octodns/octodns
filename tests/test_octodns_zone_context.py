from unittest import TestCase

from helpers import zone_validators_snapshot

from octodns.manager import Manager
from octodns.record import Record
from octodns.zone import Zone
from octodns.zone.exception import ValidationError
from octodns.zone.validator import ValidationReason, ZoneValidator


class TestZoneContext(TestCase):
    def test_zone_init_context(self):
        zone = Zone('example.com.', [], context='test-context')
        self.assertEqual(zone.context, 'test-context')

    def test_zone_copy_context(self):
        zone = Zone('example.com.', [], context='test-context')
        copy = zone.copy()
        self.assertEqual(copy.context, 'test-context')

    def test_zone_validate_context(self):
        class DummyValidator(ZoneValidator):
            def validate(self, zone):
                return [ValidationReason('test-reason', [])]

        with zone_validators_snapshot():
            Zone.register_zone_validator(DummyValidator('dummy'))
            Zone.enable_zone_validator('dummy')

            zone = Zone('example.com.', [], context='test-context')
            try:
                zone.validate()
                self.fail('Should have raised ValidationError')
            except ValidationError as e:
                self.assertEqual(e.context, 'test-context')

    def test_validation_reason_str_context(self):
        zone = Zone('example.com.', [])
        r1 = Record.new(
            zone, 'www', {'type': 'A', 'ttl': 300, 'value': '1.2.3.4'}
        )
        r1.context = 'ctx1'
        r2 = Record.new(
            zone, 'mail', {'type': 'A', 'ttl': 300, 'value': '1.2.3.5'}
        )
        r2.context = 'ctx2'

        reason = ValidationReason('problem', [r1, r2])
        self.assertIn('problem (ctx1, ctx2)', str(reason))

    def test_manager_get_zone_context(self):
        import os

        os.environ['YAML_TMP_DIR'] = '/tmp'
        os.environ['YAML_TMP_DIR2'] = '/tmp'

        class MockConfig:
            def __init__(self, data):
                self.data = data
                self.context = 'config-context'

            def get(self, key, default=None):
                return self.data.get(key, default)

        manager = Manager('tests/config/simple.yaml')
        manager.config['zones']['example.com.'] = MockConfig({})

        zone = manager.get_zone('example.com.')
        self.assertEqual(zone.context, 'config-context')
