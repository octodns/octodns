#
#
#

from unittest import TestCase

from helpers import TestZoneValidator as _TestZoneValidator
from helpers import zone_validators_snapshot

from octodns.record import Record
from octodns.zone import Zone
from octodns.zone.exception import ValidationError, ZoneException
from octodns.zone.validator import (
    ApexCaaPresenceZoneValidator,
    ApexDmarcPresenceZoneValidator,
    ApexNsPresenceZoneValidator,
    ApexSpfPresenceZoneValidator,
    CnameTargetResolvableInZoneZoneValidator,
    ConsistentTtlAtNameZoneValidator,
    GlueForInZoneNsZoneValidator,
    MultiValueApexNsZoneValidator,
    MultiValueMxZoneValidator,
    MxTargetNotCnameZoneValidator,
    MxTargetResolvableInZoneZoneValidator,
    NoCnameLoopZoneValidator,
    NoSelfReferencingTargetZoneValidator,
    NsTargetNotCnameZoneValidator,
    OverlappingSubzoneZoneValidator,
    SingleSpfZoneValidator,
    SrvTargetNotCnameZoneValidator,
    SrvTargetResolvableInZoneZoneValidator,
    ZoneValidator,
    ZoneValidatorRegistry,
)


def _make_zone(name='unit.tests.'):
    return Zone(name, [])


def _add_record(zone, name, data):
    return Record.new(zone, name, data, lenient=True)


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
        with self.assertRaises(TypeError):
            ZoneValidator()
        self.assertEqual('custom', ZoneValidator('custom').id)

    def test_validator_sets_attribute(self):
        v = ZoneValidator('test-default')
        self.assertIsNone(v.sets)

        v2 = ZoneValidator('test-custom', sets=('rfc', 'best-practice'))
        self.assertEqual({'rfc', 'best-practice'}, v2.sets)

        v3 = ZoneValidator('test-empty', sets=())
        self.assertEqual(set(), v3.sets)


class TestValidationError(TestCase):
    def test_build_message_single_reason(self):
        msg = ValidationError.build_message('unit.tests.', ['some reason'])
        self.assertIn('unit.tests', msg)
        self.assertIn('some reason', msg)

    def test_build_message_multiple_reasons(self):
        msg = ValidationError.build_message(
            'unit.tests.', ['reason one', 'reason two']
        )
        self.assertIn('reason one', msg)
        self.assertIn('reason two', msg)

    def test_build_message_with_context(self):
        msg = ValidationError.build_message(
            'unit.tests.', ['some reason'], context='some context'
        )
        self.assertIn('some context', msg)

    def test_exception_attributes(self):
        exc = ValidationError('unit.tests.', ['r1', 'r2'], context='ctx')
        self.assertEqual('unit.tests.', exc.zone_name)
        self.assertEqual(['r1', 'r2'], exc.reasons)
        self.assertEqual('ctx', exc.context)

    def test_exception_message(self):
        exc = ValidationError('unit.tests.', ['bad thing'])
        self.assertIn('unit.tests', str(exc))
        self.assertIn('bad thing', str(exc))


class TestZoneValidatorRegistry(TestCase):
    def test_register_valid(self):
        with zone_validators_snapshot():
            v = ZoneValidator('test-reg')
            Zone.validators.register(v)
            self.assertIn('test-reg', Zone.validators.available)

    def test_register_wrong_type(self):
        with zone_validators_snapshot():

            class NotAV:
                id = 'bad'

            with self.assertRaises(ZoneException) as ctx:
                Zone.validators.register(NotAV())
            self.assertIn('must be a ZoneValidator', str(ctx.exception))

    def test_register_duplicate_id(self):
        with zone_validators_snapshot():
            v = ZoneValidator('test-dup')
            Zone.validators.register(v)
            with self.assertRaises(ZoneException) as ctx:
                Zone.validators.register(ZoneValidator('test-dup'))
            self.assertIn('already registered', str(ctx.exception))

    def test_enable_sets(self):
        with zone_validators_snapshot():
            v_always = ZoneValidator('always-active')
            v_legacy = ZoneValidator('legacy-only', sets={'legacy'})
            v_best = ZoneValidator('best-practice-only', sets={'best-practice'})
            reg = ZoneValidatorRegistry()
            reg.register(v_always)
            reg.register(v_legacy)
            reg.register(v_best)

            reg.enable_sets({'legacy'})
            self.assertTrue(reg.configured)
            self.assertIn('always-active', reg.active)
            self.assertIn('legacy-only', reg.active)
            self.assertNotIn('best-practice-only', reg.active)

            reg.enable_sets({'best-practice'})
            self.assertIn('always-active', reg.active)
            self.assertNotIn('legacy-only', reg.active)
            self.assertIn('best-practice-only', reg.active)

    def test_enable_explicit(self):
        with zone_validators_snapshot():
            v = ZoneValidator('explicit', sets={'custom'})
            Zone.validators.register(v)
            Zone.validators.enable_sets({'legacy'})
            self.assertNotIn('explicit', Zone.validators.active)
            Zone.validators.enable('explicit')
            self.assertIn('explicit', Zone.validators.active)

    def test_enable_unknown(self):
        with zone_validators_snapshot():
            with self.assertRaises(ZoneException) as ctx:
                Zone.validators.enable('no-such-validator')
            self.assertIn('Unknown zone validator', str(ctx.exception))

    def test_disable(self):
        with zone_validators_snapshot():
            v = ZoneValidator('to-disable')
            Zone.validators.register(v)
            Zone.validators.enable_sets(set())
            Zone.validators.enable('to-disable')
            self.assertIn('to-disable', Zone.validators.active)
            removed = Zone.validators.disable('to-disable')
            self.assertTrue(removed)
            self.assertNotIn('to-disable', Zone.validators.active)

    def test_disable_not_active(self):
        with zone_validators_snapshot():
            Zone.validators.enable_sets({'legacy'})
            removed = Zone.validators.disable('multi-value-mx')
            self.assertFalse(removed)

    def test_disable_bridge_rejected(self):
        with zone_validators_snapshot():
            with self.assertRaises(ZoneException) as ctx:
                Zone.validators.disable('_internal')
            self.assertIn('Cannot disable bridge', str(ctx.exception))

    def test_reset_active(self):
        with zone_validators_snapshot():
            Zone.validators.enable_sets({'legacy'})
            Zone.validators.reset_active()
            self.assertEqual({}, Zone.validators.active)

    def test_registered_returns_active_list(self):
        with zone_validators_snapshot():
            v = ZoneValidator('reg-test')
            Zone.validators.register(v)
            Zone.validators.enable_sets(set())
            Zone.validators.enable('reg-test')
            self.assertIn(v, Zone.validators.registered())

    def test_available_validators(self):
        with zone_validators_snapshot():
            avail = Zone.validators.available_validators()
            ids = [v.id for v in avail]
            self.assertIn('multi-value-mx', ids)
            self.assertIn('apex-spf-presence', ids)

    def test_process_zone_lazy_init(self):
        with zone_validators_snapshot():
            reg = ZoneValidatorRegistry()
            zone = _make_zone()
            with self.assertLogs('Zone', level='WARNING') as logs:
                reg.process_zone(zone)
            self.assertTrue(reg.configured)
            self.assertTrue(
                any(
                    'automatically enabling legacy set' in m
                    for m in logs.output
                )
            )

    def test_process_zone_collects_reasons(self):
        with zone_validators_snapshot():
            reasons_returned = ['reason one', 'reason two']

            class FailingValidator(ZoneValidator):
                def validate(self, zone):
                    return reasons_returned

            reg = ZoneValidatorRegistry()
            reg.register(FailingValidator('failing'))
            reg.enable_sets(set())
            reg.enable('failing')
            zone = _make_zone()
            result = reg.process_zone(zone)
            self.assertEqual(reasons_returned, result)

    def test_process_zone_no_active_no_reasons(self):
        with zone_validators_snapshot():
            reg = ZoneValidatorRegistry()
            reg.enable_sets(set())
            zone = _make_zone()
            result = reg.process_zone(zone)
            self.assertEqual([], result)


class TestZoneClassmethods(TestCase):
    def test_register_zone_validator(self):
        with zone_validators_snapshot():
            v = ZoneValidator('cm-test')
            Zone.register_zone_validator(v)
            self.assertIn('cm-test', Zone.validators.available)

    def test_enable_zone_validators(self):
        with zone_validators_snapshot():
            Zone.enable_zone_validators({'legacy'})
            self.assertTrue(Zone.validators.configured)

    def test_enable_zone_validator(self):
        with zone_validators_snapshot():
            v = ZoneValidator('cm-enable', sets={'custom'})
            Zone.register_zone_validator(v)
            Zone.enable_zone_validators(set())
            Zone.enable_zone_validator('cm-enable')
            self.assertIn('cm-enable', Zone.validators.active)

    def test_disable_zone_validator(self):
        with zone_validators_snapshot():
            v = ZoneValidator('cm-disable')
            Zone.register_zone_validator(v)
            Zone.enable_zone_validators(set())
            Zone.enable_zone_validator('cm-disable')
            removed = Zone.disable_zone_validator('cm-disable')
            self.assertTrue(removed)
            self.assertNotIn('cm-disable', Zone.validators.active)

    def test_registered_zone_validators(self):
        with zone_validators_snapshot():
            Zone.enable_zone_validators(set())
            self.assertEqual([], Zone.registered_zone_validators())

    def test_available_zone_validators(self):
        with zone_validators_snapshot():
            avail = Zone.available_zone_validators()
            self.assertIsInstance(avail, list)
            ids = [v.id for v in avail]
            self.assertIn('multi-value-mx', ids)


class TestZoneValidateMethod(TestCase):
    def test_validate_passes_clean_zone(self):
        with zone_validators_snapshot():
            Zone.enable_zone_validators(set())
            zone = _make_zone()
            zone.validate()

    def test_validate_raises_on_failure(self):
        with zone_validators_snapshot():

            class FailValidator(ZoneValidator):
                def validate(self, zone):
                    return ['zone has a problem']

            reg_v = FailValidator('fail-test')
            Zone.register_zone_validator(reg_v)
            Zone.enable_zone_validators(set())
            Zone.enable_zone_validator('fail-test')
            zone = _make_zone()
            with self.assertRaises(ValidationError) as ctx:
                zone.validate()
            self.assertIn('zone has a problem', str(ctx.exception))

    def test_validate_lenient_warns_not_raises(self):
        with zone_validators_snapshot():

            class FailValidator(ZoneValidator):
                def validate(self, zone):
                    return ['zone has a problem']

            reg_v = FailValidator('fail-lenient')
            Zone.register_zone_validator(reg_v)
            Zone.enable_zone_validators(set())
            Zone.enable_zone_validator('fail-lenient')
            zone = _make_zone()
            with self.assertLogs('Zone', level='WARNING') as logs:
                zone.validate(lenient=True)
            self.assertTrue(any('zone has a problem' in m for m in logs.output))


class TestBuiltinZoneValidators(TestCase):
    def test_multi_value_mx_passes_two_values(self):
        zone = _make_zone()
        mx = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [
                    {'preference': 10, 'exchange': 'mail1.unit.tests.'},
                    {'preference': 20, 'exchange': 'mail2.unit.tests.'},
                ],
            },
        )
        zone.add_record(mx, replace=True)
        v = MultiValueMxZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_multi_value_mx_fails_single_value(self):
        zone = _make_zone()
        mx = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [{'preference': 10, 'exchange': 'mail1.unit.tests.'}],
            },
        )
        zone.add_record(mx, replace=True)
        v = MultiValueMxZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('at least 2 values', reasons[0])
        self.assertIn('unit.tests.', reasons[0])

    def test_multi_value_mx_no_mx_records(self):
        zone = _make_zone()
        v = MultiValueMxZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_multi_value_mx_non_apex_mx(self):
        zone = _make_zone()
        mx = _add_record(
            zone,
            'sub',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [{'preference': 10, 'exchange': 'mail1.unit.tests.'}],
            },
        )
        zone.add_record(mx)
        v = MultiValueMxZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('sub.unit.tests.', reasons[0])

    def test_apex_spf_presence_passes(self):
        zone = _make_zone()
        txt = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'TXT',
                'values': ['v=spf1 include:example.com ~all', 'some-other-txt'],
            },
        )
        zone.add_record(txt, replace=True)
        v = ApexSpfPresenceZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_apex_spf_presence_fails_no_txt(self):
        zone = _make_zone()
        v = ApexSpfPresenceZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('no TXT records', reasons[0])

    def test_apex_spf_presence_fails_no_spf_value(self):
        zone = _make_zone()
        txt = _add_record(
            zone,
            '',
            {'ttl': 300, 'type': 'TXT', 'values': ['google-site-verify=abc']},
        )
        zone.add_record(txt, replace=True)
        v = ApexSpfPresenceZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('v=spf1', reasons[0])

    def test_apex_spf_presence_passes_multiple_values(self):
        zone = _make_zone()
        txt = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'TXT',
                'values': ['something', 'v=spf1 include:example.com ~all'],
            },
        )
        zone.add_record(txt)
        v = ApexSpfPresenceZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_apex_dmarc_presence_passes(self):
        zone = _make_zone()
        txt = _add_record(
            zone,
            '_dmarc',
            {'ttl': 300, 'type': 'TXT', 'values': ['v=DMARC1; p=none']},
        )
        zone.add_record(txt)
        v = ApexDmarcPresenceZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_apex_dmarc_presence_fails_no_txt(self):
        zone = _make_zone()
        v = ApexDmarcPresenceZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('no TXT records at "_dmarc"', reasons[0])

    def test_apex_dmarc_presence_fails_no_dmarc_value(self):
        zone = _make_zone()
        txt = _add_record(
            zone, '_dmarc', {'ttl': 300, 'type': 'TXT', 'values': ['something']}
        )
        zone.add_record(txt)
        v = ApexDmarcPresenceZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('v=DMARC1', reasons[0])

    def test_no_cname_loop_passes(self):
        zone = _make_zone()
        cname = _add_record(
            zone,
            'www',
            {'ttl': 300, 'type': 'CNAME', 'value': 'lb.unit.tests.'},
        )
        zone.add_record(cname)
        v = NoCnameLoopZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_no_cname_loop_fails_direct(self):
        zone = _make_zone()
        cname = _add_record(
            zone,
            'loop',
            {'ttl': 300, 'type': 'CNAME', 'value': 'loop.unit.tests.'},
        )
        zone.add_record(cname)
        v = NoCnameLoopZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('Loop detected', reasons[0])
        self.assertIn('loop.unit.tests. -> loop.unit.tests.', reasons[0])

    def test_no_cname_loop_fails_indirect(self):
        zone = _make_zone()
        c1 = _add_record(
            zone, 'a', {'ttl': 300, 'type': 'CNAME', 'value': 'b.unit.tests.'}
        )
        c2 = _add_record(
            zone, 'b', {'ttl': 300, 'type': 'CNAME', 'value': 'c.unit.tests.'}
        )
        c3 = _add_record(
            zone, 'c', {'ttl': 300, 'type': 'CNAME', 'value': 'a.unit.tests.'}
        )
        zone.add_record(c1)
        zone.add_record(c2)
        zone.add_record(c3)
        v = NoCnameLoopZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('Loop detected', reasons[0])
        self.assertIn('a.unit.tests.', reasons[0])
        self.assertIn('b.unit.tests.', reasons[0])
        self.assertIn('c.unit.tests.', reasons[0])

    def test_no_cname_loop_with_alias(self):
        zone = _make_zone()
        a1 = _add_record(
            zone, '', {'ttl': 300, 'type': 'ALIAS', 'value': 'b.unit.tests.'}
        )
        c2 = _add_record(
            zone, 'b', {'ttl': 300, 'type': 'CNAME', 'value': 'unit.tests.'}
        )
        zone.add_record(a1)
        zone.add_record(c2)
        v = NoCnameLoopZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('Loop detected', reasons[0])
        self.assertIn('unit.tests.', reasons[0])
        self.assertIn('b.unit.tests.', reasons[0])

    def test_no_cname_loop_merging_chains(self):
        # Hits the "if curr in overall_visited: break" path
        zone = _make_zone()
        c1 = _add_record(
            zone, 'x', {'ttl': 300, 'type': 'CNAME', 'value': 'z.unit.tests.'}
        )
        c2 = _add_record(
            zone, 'y', {'ttl': 300, 'type': 'CNAME', 'value': 'z.unit.tests.'}
        )
        c3 = _add_record(
            zone, 'z', {'ttl': 300, 'type': 'CNAME', 'value': 'end.unit.tests.'}
        )
        zone.add_record(c1)
        zone.add_record(c2)
        zone.add_record(c3)
        v = NoCnameLoopZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_consistent_ttl_at_name_passes(self):
        zone = _make_zone()
        a = _add_record(
            zone, 'www', {'ttl': 300, 'type': 'A', 'value': '1.2.3.4'}
        )
        aaaa = _add_record(
            zone, 'www', {'ttl': 300, 'type': 'AAAA', 'value': '::1'}
        )
        zone.add_record(a)
        zone.add_record(aaaa)
        v = ConsistentTtlAtNameZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_consistent_ttl_at_name_single_record(self):
        zone = _make_zone()
        a = _add_record(
            zone, 'www', {'ttl': 300, 'type': 'A', 'value': '1.2.3.4'}
        )
        zone.add_record(a)
        v = ConsistentTtlAtNameZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_consistent_ttl_at_name_fails(self):
        zone = _make_zone()
        a = _add_record(
            zone, 'www', {'ttl': 300, 'type': 'A', 'value': '1.2.3.4'}
        )
        aaaa = _add_record(
            zone, 'www', {'ttl': 600, 'type': 'AAAA', 'value': '::1'}
        )
        zone.add_record(a)
        zone.add_record(aaaa)
        v = ConsistentTtlAtNameZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('Inconsistent TTLs at "www.unit.tests."', reasons[0])
        self.assertIn('[300, 600]', reasons[0])

    def test_consistent_ttl_at_name_fails_apex(self):
        zone = _make_zone()
        a = _add_record(zone, '', {'ttl': 300, 'type': 'A', 'value': '1.2.3.4'})
        mx = _add_record(
            zone,
            '',
            {
                'ttl': 600,
                'type': 'MX',
                'values': [{'preference': 10, 'exchange': 'mail.unit.tests.'}],
            },
        )
        zone.add_record(a)
        zone.add_record(mx, replace=True)
        v = ConsistentTtlAtNameZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('Inconsistent TTLs at "unit.tests."', reasons[0])

    def test_glue_for_in_zone_ns_passes_external(self):
        zone = _make_zone()
        ns = _add_record(
            zone,
            '',
            {'ttl': 3600, 'type': 'NS', 'values': ['ns1.external.tests.']},
        )
        zone.add_record(ns, replace=True)
        v = GlueForInZoneNsZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_glue_for_in_zone_ns_no_ns_records(self):
        zone = _make_zone()
        a = _add_record(
            zone, 'www', {'ttl': 300, 'type': 'A', 'value': '1.2.3.4'}
        )
        zone.add_record(a)
        v = GlueForInZoneNsZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_glue_for_in_zone_ns_passes_with_glue(self):
        zone = _make_zone()
        ns = _add_record(
            zone, '', {'ttl': 3600, 'type': 'NS', 'values': ['ns1.unit.tests.']}
        )
        a = _add_record(
            zone, 'ns1', {'ttl': 3600, 'type': 'A', 'value': '1.2.3.4'}
        )
        zone.add_record(ns, replace=True)
        zone.add_record(a)
        v = GlueForInZoneNsZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_glue_for_in_zone_ns_passes_with_aaaa_glue(self):
        zone = _make_zone()
        ns = _add_record(
            zone, '', {'ttl': 3600, 'type': 'NS', 'values': ['ns1.unit.tests.']}
        )
        aaaa = _add_record(
            zone, 'ns1', {'ttl': 3600, 'type': 'AAAA', 'value': '::1'}
        )
        zone.add_record(ns, replace=True)
        zone.add_record(aaaa)
        v = GlueForInZoneNsZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_glue_for_in_zone_ns_fails_missing_glue(self):
        zone = _make_zone()
        ns = _add_record(
            zone, '', {'ttl': 3600, 'type': 'NS', 'values': ['ns1.unit.tests.']}
        )
        zone.add_record(ns, replace=True)
        v = GlueForInZoneNsZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('without glue records', reasons[0])

    def test_single_spf_passes(self):
        zone = _make_zone()
        txt = _add_record(
            zone, '', {'ttl': 300, 'type': 'TXT', 'values': ['v=spf1 -all']}
        )
        zone.add_record(txt, replace=True)
        v = SingleSpfZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_single_spf_fails(self):
        zone = _make_zone()
        txt = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'TXT',
                'values': [
                    'v=spf1 include:a.com ~all',
                    'v=spf1 include:b.com ~all',
                ],
            },
        )
        zone.add_record(txt, replace=True)
        v = SingleSpfZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('has 2 SPF records', reasons[0])

    def test_single_spf_with_non_spf_txt(self):
        zone = _make_zone()
        txt = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'TXT',
                'values': ['v=spf1 -all', 'something-else'],
            },
        )
        zone.add_record(txt, replace=True)
        v = SingleSpfZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_no_self_referencing_target_passes(self):
        zone = _make_zone()
        cname = _add_record(
            zone,
            'www',
            {'ttl': 300, 'type': 'CNAME', 'value': 'lb.unit.tests.'},
        )
        mx = _add_record(
            zone,
            'mail',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [{'preference': 10, 'exchange': 'other.unit.tests.'}],
            },
        )
        ns = _add_record(
            zone,
            'ns',
            {'ttl': 300, 'type': 'NS', 'values': ['other.unit.tests.']},
        )
        srv = _add_record(
            zone,
            '_sip',
            {
                'ttl': 300,
                'type': 'SRV',
                'values': [
                    {
                        'priority': 10,
                        'weight': 10,
                        'port': 5060,
                        'target': 'sip.unit.tests.',
                    }
                ],
            },
        )
        zone.add_record(cname)
        zone.add_record(mx)
        zone.add_record(ns)
        zone.add_record(srv)
        v = NoSelfReferencingTargetZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_no_self_referencing_target_fails(self):
        zone = _make_zone()
        cname = _add_record(
            zone,
            'www',
            {'ttl': 300, 'type': 'CNAME', 'value': 'www.unit.tests.'},
        )
        alias = _add_record(
            zone, '', {'ttl': 300, 'type': 'ALIAS', 'value': 'unit.tests.'}
        )
        mx = _add_record(
            zone,
            'mail',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [{'preference': 10, 'exchange': 'mail.unit.tests.'}],
            },
        )
        ns = _add_record(
            zone, 'ns', {'ttl': 300, 'type': 'NS', 'values': ['ns.unit.tests.']}
        )
        ptr = _add_record(
            zone, 'ptr', {'ttl': 300, 'type': 'PTR', 'value': 'ptr.unit.tests.'}
        )
        srv = _add_record(
            zone,
            '_sip._tcp',
            {
                'ttl': 300,
                'type': 'SRV',
                'values': [
                    {
                        'priority': 10,
                        'weight': 10,
                        'port': 5060,
                        'target': '_sip._tcp.unit.tests.',
                    }
                ],
            },
        )
        zone.add_record(cname)
        zone.add_record(alias, replace=True)
        zone.add_record(mx)
        zone.add_record(ns)
        zone.add_record(ptr)
        zone.add_record(srv)
        v = NoSelfReferencingTargetZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(6, len(reasons))
        self.assertIn(
            'CNAME record "www.unit.tests." points to itself', reasons
        )
        self.assertIn('ALIAS record "unit.tests." points to itself', reasons)
        self.assertIn('MX record "mail.unit.tests." points to itself', reasons)
        self.assertIn('NS record "ns.unit.tests." points to itself', reasons)
        self.assertIn('PTR record "ptr.unit.tests." points to itself', reasons)
        self.assertIn(
            'SRV record "_sip._tcp.unit.tests." points to itself', reasons
        )

    def test_cname_target_resolvable_in_zone_passes(self):
        zone = _make_zone()
        cname = _add_record(
            zone,
            'www',
            {'ttl': 300, 'type': 'CNAME', 'value': 'lb.unit.tests.'},
        )
        a = _add_record(
            zone, 'lb', {'ttl': 300, 'type': 'A', 'value': '1.2.3.4'}
        )
        zone.add_record(cname)
        zone.add_record(a)
        v = CnameTargetResolvableInZoneZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_cname_target_resolvable_in_zone_skip_out_of_zone(self):
        zone = _make_zone()
        cname = _add_record(
            zone, 'www', {'ttl': 300, 'type': 'CNAME', 'value': 'google.com.'}
        )
        zone.add_record(cname)
        v = CnameTargetResolvableInZoneZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_cname_target_resolvable_in_zone_fails(self):
        zone = _make_zone()
        cname = _add_record(
            zone,
            'www',
            {'ttl': 300, 'type': 'CNAME', 'value': 'lb.unit.tests.'},
        )
        alias = _add_record(
            zone,
            'a',
            {'ttl': 300, 'type': 'ALIAS', 'value': 'missing.unit.tests.'},
        )
        zone.add_record(cname)
        zone.add_record(alias)
        v = CnameTargetResolvableInZoneZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(2, len(reasons))
        self.assertIn(
            'CNAME record "www.unit.tests." points to in-zone target "lb.unit.tests." that does not exist',
            reasons,
        )
        self.assertIn(
            'ALIAS record "a.unit.tests." points to in-zone target "missing.unit.tests." that does not exist',
            reasons,
        )

    def test_target_not_cname_passes(self):
        zone = _make_zone()
        mx = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [{'preference': 10, 'exchange': 'mail.unit.tests.'}],
            },
        )
        a = _add_record(
            zone, 'mail', {'ttl': 300, 'type': 'A', 'value': '1.2.3.4'}
        )
        zone.add_record(mx, replace=True)
        zone.add_record(a)
        v = MxTargetNotCnameZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_target_not_cname_skip_out_of_zone(self):
        zone = _make_zone()
        mx = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [{'preference': 10, 'exchange': 'google.com.'}],
            },
        )
        zone.add_record(mx, replace=True)
        v = MxTargetNotCnameZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_target_not_cname_skip_no_cname_at_target(self):
        zone = _make_zone()
        mx = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [
                    {'preference': 10, 'exchange': 'target.unit.tests.'}
                ],
            },
        )
        # target exists but is not a CNAME (it's an A record)
        a = _add_record(
            zone, 'target', {'ttl': 300, 'type': 'A', 'value': '1.2.3.4'}
        )
        zone.add_record(mx, replace=True)
        zone.add_record(a)
        v = MxTargetNotCnameZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_target_not_cname_fails(self):
        zone = _make_zone()
        mx = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [
                    {'preference': 10, 'exchange': 'mail1.unit.tests.'},
                    {'preference': 20, 'exchange': 'mail2.unit.tests.'},
                ],
            },
        )
        cname = _add_record(
            zone,
            'mail1',
            {'ttl': 300, 'type': 'CNAME', 'value': 'other.unit.tests.'},
        )
        zone.add_record(mx, replace=True)
        zone.add_record(cname)
        v = MxTargetNotCnameZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn(
            'points to in-zone target "mail1.unit.tests." which is a CNAME',
            reasons[0],
        )

    def test_ns_target_not_cname_fails(self):
        zone = _make_zone()
        ns = _add_record(
            zone, '', {'ttl': 3600, 'type': 'NS', 'values': ['ns1.unit.tests.']}
        )
        cname = _add_record(
            zone,
            'ns1',
            {'ttl': 300, 'type': 'CNAME', 'value': 'other.unit.tests.'},
        )
        zone.add_record(ns, replace=True)
        zone.add_record(cname)
        v = NsTargetNotCnameZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn(
            'NS record "unit.tests." points to in-zone target "ns1.unit.tests." which is a CNAME',
            reasons[0],
        )

    def test_target_not_cname_alias_target_fails(self):
        zone = _make_zone()
        mx = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [
                    {'preference': 10, 'exchange': 'target.unit.tests.'}
                ],
            },
        )
        cname = _add_record(
            zone,
            'target',
            {'ttl': 300, 'type': 'CNAME', 'value': 'other.unit.tests.'},
        )
        zone.add_record(mx, replace=True)
        zone.add_record(cname)
        v = MxTargetNotCnameZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn(
            'points to in-zone target "target.unit.tests." which is a CNAME',
            reasons[0],
        )

    def test_srv_target_not_cname_fails(self):
        zone = _make_zone()
        srv = _add_record(
            zone,
            '_sip._tcp',
            {
                'ttl': 300,
                'type': 'SRV',
                'values': [
                    {
                        'priority': 10,
                        'weight': 10,
                        'port': 5060,
                        'target': 'sip.unit.tests.',
                    }
                ],
            },
        )
        cname = _add_record(
            zone,
            'sip',
            {'ttl': 300, 'type': 'CNAME', 'value': 'other.unit.tests.'},
        )
        zone.add_record(srv)
        zone.add_record(cname)
        v = SrvTargetNotCnameZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn(
            'SRV record "_sip._tcp.unit.tests." points to in-zone target "sip.unit.tests." which is a CNAME',
            reasons[0],
        )

    def test_apex_ns_presence_passes(self):
        zone = _make_zone()
        ns = _add_record(
            zone, '', {'ttl': 3600, 'type': 'NS', 'values': ['ns1.unit.tests.']}
        )
        zone.add_record(ns, replace=True)
        v = ApexNsPresenceZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_apex_ns_presence_fails(self):
        zone = _make_zone()
        v = ApexNsPresenceZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('missing NS records at the apex', reasons[0])

    def test_multi_value_apex_ns_passes(self):
        zone = _make_zone()
        ns = _add_record(
            zone,
            '',
            {
                'ttl': 3600,
                'type': 'NS',
                'values': ['ns1.unit.tests.', 'ns2.unit.tests.'],
            },
        )
        zone.add_record(ns, replace=True)
        v = MultiValueApexNsZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_multi_value_apex_ns_fails(self):
        zone = _make_zone()
        ns = _add_record(
            zone, '', {'ttl': 3600, 'type': 'NS', 'values': ['ns1.unit.tests.']}
        )
        zone.add_record(ns, replace=True)
        v = MultiValueApexNsZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('has only 1 NS record', reasons[0])

    def test_multi_value_apex_ns_skips_missing(self):
        zone = _make_zone()
        v = MultiValueApexNsZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_overlapping_subzone_passes(self):
        zone = _make_zone()
        ns = _add_record(
            zone, 'sub', {'ttl': 3600, 'type': 'NS', 'values': ['ns1.other.']}
        )
        a = _add_record(
            zone, 'www', {'ttl': 300, 'type': 'A', 'value': '1.2.3.4'}
        )
        zone.add_record(ns)
        zone.add_record(a)
        v = OverlappingSubzoneZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_overlapping_subzone_fails(self):
        zone = _make_zone()
        ns = _add_record(
            zone, 'sub', {'ttl': 3600, 'type': 'NS', 'values': ['ns1.other.']}
        )
        a = _add_record(
            zone, 'www.sub', {'ttl': 300, 'type': 'A', 'value': '1.2.3.4'}
        )
        zone.add_record(ns)
        zone.add_record(a)
        v = OverlappingSubzoneZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('shadowed by delegation at "sub.unit.tests."', reasons[0])

    def test_apex_caa_presence_passes(self):
        zone = _make_zone()
        caa = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'CAA',
                'values': [
                    {'flags': 0, 'tag': 'issue', 'value': 'letsencrypt.org'}
                ],
            },
        )
        zone.add_record(caa)
        v = ApexCaaPresenceZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_apex_caa_presence_fails(self):
        zone = _make_zone()
        v = ApexCaaPresenceZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn('has no CAA records at the apex', reasons[0])

    def test_mx_target_resolvable_in_zone_passes(self):
        zone = _make_zone()
        mx = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [{'preference': 10, 'exchange': 'mail.unit.tests.'}],
            },
        )
        a = _add_record(
            zone, 'mail', {'ttl': 300, 'type': 'A', 'value': '1.2.3.4'}
        )
        zone.add_record(mx, replace=True)
        zone.add_record(a)
        v = MxTargetResolvableInZoneZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_mx_target_resolvable_in_zone_fails(self):
        zone = _make_zone()
        mx = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [{'preference': 10, 'exchange': 'mail.unit.tests.'}],
            },
        )
        zone.add_record(mx, replace=True)
        v = MxTargetResolvableInZoneZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn(
            'points to in-zone target "mail.unit.tests." that does not exist',
            reasons[0],
        )

    def test_mx_target_resolvable_in_zone_skip_out_of_zone(self):
        zone = _make_zone()
        mx = _add_record(
            zone,
            '',
            {
                'ttl': 300,
                'type': 'MX',
                'values': [{'preference': 10, 'exchange': 'google.com.'}],
            },
        )
        zone.add_record(mx, replace=True)
        v = MxTargetResolvableInZoneZoneValidator('test')
        self.assertEqual([], v.validate(zone))

    def test_srv_target_resolvable_in_zone_fails(self):
        zone = _make_zone()
        srv = _add_record(
            zone,
            '_sip._tcp',
            {
                'ttl': 300,
                'type': 'SRV',
                'values': [
                    {
                        'priority': 10,
                        'weight': 10,
                        'port': 5060,
                        'target': 'sip.unit.tests.',
                    }
                ],
            },
        )
        zone.add_record(srv)
        v = SrvTargetResolvableInZoneZoneValidator('test')
        reasons = v.validate(zone)
        self.assertEqual(1, len(reasons))
        self.assertIn(
            'points to in-zone target "sip.unit.tests." that does not exist',
            reasons[0],
        )

    def test_builtin_ids(self):
        ids = [v.id for v in Zone.validators.available_validators()]
        self.assertIn('multi-value-mx', ids)
        self.assertIn('apex-spf-presence', ids)
        self.assertIn('apex-dmarc-presence', ids)
        self.assertIn('no-cname-loop', ids)
        self.assertIn('consistent-ttl-at-name', ids)
        self.assertIn('glue-for-in-zone-ns', ids)
        self.assertIn('single-spf', ids)
        self.assertIn('no-self-referencing-target', ids)
        self.assertIn('cname-target-resolvable-in-zone', ids)
        self.assertIn('ns-target-not-cname', ids)
        self.assertIn('mx-target-not-cname', ids)
        self.assertIn('srv-target-not-cname', ids)
        self.assertIn('apex-ns-presence', ids)
        self.assertIn('multi-value-apex-ns', ids)
        self.assertIn('overlapping-subzone', ids)
        self.assertIn('apex-caa-presence', ids)
        self.assertIn('mx-target-resolvable-in-zone', ids)
        self.assertIn('srv-target-resolvable-in-zone', ids)

    def test_builtins_in_best_practice_set(self):
        with zone_validators_snapshot():
            Zone.enable_zone_validators({'best-practice'})
            active_ids = [v.id for v in Zone.validators.registered()]
            self.assertIn('multi-value-mx', active_ids)
            self.assertIn('apex-spf-presence', active_ids)
            self.assertIn('apex-ns-presence', active_ids)
            self.assertNotIn('overlapping-subzone', active_ids)

    def test_builtins_in_strict_set(self):
        with zone_validators_snapshot():
            Zone.enable_zone_validators({'strict'})
            active_ids = [v.id for v in Zone.validators.registered()]
            self.assertIn('overlapping-subzone', active_ids)
            self.assertNotIn('apex-ns-presence', active_ids)

    def test_builtins_not_in_legacy_set(self):
        with zone_validators_snapshot():
            Zone.enable_zone_validators({'legacy'})
            active_ids = [v.id for v in Zone.validators.registered()]
            self.assertNotIn('multi-value-mx', active_ids)
            self.assertNotIn('apex-spf-presence', active_ids)

    def test_test_zone_validator_helper(self):
        with zone_validators_snapshot():
            v = _TestZoneValidator('helper-test', require_mx=True)
            zone = _make_zone()
            reasons = v.validate(zone)
            self.assertEqual(1, len(reasons))
            self.assertIn('MX record', reasons[0])

            mx = _add_record(
                zone,
                '',
                {
                    'ttl': 300,
                    'type': 'MX',
                    'values': [
                        {'preference': 10, 'exchange': 'mail1.unit.tests.'}
                    ],
                },
            )
            zone.add_record(mx, replace=True)
            self.assertEqual([], v.validate(zone))
