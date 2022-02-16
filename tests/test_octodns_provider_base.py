#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger
from unittest import TestCase
from unittest.mock import MagicMock, call

from octodns.processor.base import BaseProcessor
from octodns.provider import SupportsException
from octodns.provider.base import BaseProvider
from octodns.provider.plan import Plan, UnsafePlan
from octodns.record import Create, Delete, Record, Update
from octodns.zone import Zone


class HelperProvider(BaseProvider):
    log = getLogger('HelperProvider')

    SUPPORTS = set(('A', 'NS', 'PTR'))
    SUPPORTS_MULTIVALUE_PTR = False
    SUPPORTS_DYNAMIC = False

    id = 'test'
    strict_supports = False

    def __init__(self, extra_changes=[], apply_disabled=False,
                 include_change_callback=None):
        self.__extra_changes = extra_changes
        self.apply_disabled = apply_disabled
        self.include_change_callback = include_change_callback
        self.update_pcent_threshold = Plan.MAX_SAFE_UPDATE_PCENT
        self.delete_pcent_threshold = Plan.MAX_SAFE_DELETE_PCENT

    def populate(self, zone, target=False, lenient=False):
        return True

    def _include_change(self, change):
        return not self.include_change_callback or \
            self.include_change_callback(change)

    def _extra_changes(self, **kwargs):
        return self.__extra_changes

    def _apply(self, plan):
        pass


class TrickyProcessor(BaseProcessor):

    def __init__(self, name, add_during_process_target_zone):
        super(TrickyProcessor, self).__init__(name)
        self.add_during_process_target_zone = add_during_process_target_zone
        self.reset()

    def reset(self):
        self.existing = None
        self.target = None

    def process_target_zone(self, existing, target):
        self.existing = existing
        self.target = target

        new = existing.copy()
        for record in existing.records:
            new.add_record(record, replace=True)
        for record in self.add_during_process_target_zone:
            new.add_record(record, replace=True)
        return new


class TestBaseProvider(TestCase):

    def test_base_provider(self):
        with self.assertRaises(NotImplementedError) as ctx:
            BaseProvider('base')
        self.assertEqual('Abstract base class, log property missing',
                         str(ctx.exception))

        class HasLog(BaseProvider):
            log = getLogger('HasLog')

        with self.assertRaises(NotImplementedError) as ctx:
            HasLog('haslog')
        self.assertEqual('Abstract base class, SUPPORTS_GEO property missing',
                         str(ctx.exception))

        class HasSupportsGeo(HasLog):
            SUPPORTS_GEO = False

        zone = Zone('unit.tests.', ['sub'])
        with self.assertRaises(NotImplementedError) as ctx:
            HasSupportsGeo('hassupportsgeo').populate(zone)
        self.assertEqual('Abstract base class, SUPPORTS property missing',
                         str(ctx.exception))

        class HasSupports(HasSupportsGeo):
            SUPPORTS = set(('A',))
        with self.assertRaises(NotImplementedError) as ctx:
            HasSupports('hassupports').populate(zone)
        self.assertEqual('Abstract base class, populate method missing',
                         str(ctx.exception))

        # SUPPORTS_DYNAMIC has a default/fallback
        self.assertFalse(HasSupports('hassupports').SUPPORTS_DYNAMIC)

        # But can be overridden
        class HasSupportsDyanmic(HasSupports):
            SUPPORTS_DYNAMIC = True

        self.assertTrue(HasSupportsDyanmic('hassupportsdynamic')
                        .SUPPORTS_DYNAMIC)

        class HasPopulate(HasSupports):

            def populate(self, zone, target=False, lenient=False):
                zone.add_record(Record.new(zone, '', {
                    'ttl': 60,
                    'type': 'A',
                    'value': '2.3.4.5'
                }), lenient=lenient)
                zone.add_record(Record.new(zone, 'going', {
                    'ttl': 60,
                    'type': 'A',
                    'value': '3.4.5.6'
                }), lenient=lenient)
                zone.add_record(Record.new(zone, 'foo.sub', {
                    'ttl': 61,
                    'type': 'A',
                    'value': '4.5.6.7'
                }), lenient=lenient)

        zone.add_record(Record.new(zone, '', {
            'ttl': 60,
            'type': 'A',
            'value': '1.2.3.4'
        }))

        self.assertTrue(HasSupports('hassupportsgeo')
                        .supports(list(zone.records)[0]))

        plan = HasPopulate('haspopulate').plan(zone)
        self.assertEqual(3, len(plan.changes))

        with self.assertRaises(NotImplementedError) as ctx:
            HasPopulate('haspopulate').apply(plan)
        self.assertEqual('Abstract base class, _apply method missing',
                         str(ctx.exception))

    def test_plan(self):
        ignored = Zone('unit.tests.', [])

        # No change, thus no plan
        provider = HelperProvider([])
        self.assertEqual(None, provider.plan(ignored))

        record = Record.new(ignored, 'a', {
            'ttl': 30,
            'type': 'A',
            'value': '1.2.3.4',
        })
        provider = HelperProvider([Create(record)])
        plan = provider.plan(ignored)
        self.assertTrue(plan)
        self.assertEqual(1, len(plan.changes))

    def test_plan_with_unsupported_type(self):
        zone = Zone('unit.tests.', [])

        # supported
        supported = Record.new(zone, 'a', {
            'ttl': 30,
            'type': 'A',
            'value': '1.2.3.4',
        })
        zone.add_record(supported)
        # not supported
        not_supported = Record.new(zone, 'aaaa', {
            'ttl': 30,
            'type': 'AAAA',
            'value': '2601:644:500:e210:62f8:1dff:feb8:947a',
        })
        zone.add_record(not_supported)
        provider = HelperProvider()
        plan = provider.plan(zone)
        self.assertTrue(plan)
        self.assertEqual(1, len(plan.changes))
        self.assertEqual(supported, plan.changes[0].new)

    def test_plan_with_processors(self):
        zone = Zone('unit.tests.', [])

        record = Record.new(zone, 'a', {
            'ttl': 30,
            'type': 'A',
            'value': '1.2.3.4',
        })
        provider = HelperProvider()
        # Processor that adds a record to the zone, which planning will then
        # delete since it won't know anything about it
        tricky = TrickyProcessor('tricky', [record])
        plan = provider.plan(zone, processors=[tricky])
        self.assertTrue(plan)
        self.assertEqual(1, len(plan.changes))
        self.assertIsInstance(plan.changes[0], Delete)
        # Called processor stored its params
        self.assertTrue(tricky.existing)
        self.assertEqual(zone.name, tricky.existing.name)

        # Chain of processors happen one after the other
        other = Record.new(zone, 'b', {
            'ttl': 30,
            'type': 'A',
            'value': '5.6.7.8',
        })
        # Another processor will add its record, thus 2 deletes
        another = TrickyProcessor('tricky', [other])
        plan = provider.plan(zone, processors=[tricky, another])
        self.assertTrue(plan)
        self.assertEqual(2, len(plan.changes))
        self.assertIsInstance(plan.changes[0], Delete)
        self.assertIsInstance(plan.changes[1], Delete)
        # 2nd processor stored its params, and we'll see the record the
        # first one added
        self.assertTrue(another.existing)
        self.assertEqual(zone.name, another.existing.name)
        self.assertEqual(1, len(another.existing.records))

    def test_plan_with_root_ns(self):
        zone = Zone('unit.tests.', [])
        record = Record.new(zone, '', {
            'ttl': 30,
            'type': 'NS',
            'value': '1.2.3.4.',
        })
        zone.add_record(record)

        # No root NS support, no change, thus no plan
        provider = HelperProvider()
        self.assertEqual(None, provider.plan(zone))

        # set Support root NS records, see the record
        provider.SUPPORTS_ROOT_NS = True
        plan = provider.plan(zone)
        self.assertTrue(plan)
        self.assertEqual(1, len(plan.changes))

    def test_apply(self):
        ignored = Zone('unit.tests.', [])

        record = Record.new(ignored, 'a', {
            'ttl': 30,
            'type': 'A',
            'value': '1.2.3.4',
        })
        provider = HelperProvider([Create(record)], apply_disabled=True)
        plan = provider.plan(ignored)
        provider.apply(plan)

        provider.apply_disabled = False
        self.assertEqual(1, provider.apply(plan))

    def test_include_change(self):
        zone = Zone('unit.tests.', [])

        record = Record.new(zone, 'a', {
            'ttl': 30,
            'type': 'A',
            'value': '1.2.3.4',
        })
        zone.add_record(record)
        provider = HelperProvider([], include_change_callback=lambda c: False)
        plan = provider.plan(zone)
        # We filtered out the only change
        self.assertFalse(plan)

    def test_plan_order_of_operations(self):

        class MockProvider(BaseProvider):
            log = getLogger('mock-provider')
            SUPPORTS = set(('A',))
            SUPPORTS_GEO = False

            def __init__(self):
                super().__init__('mock-provider')
                self.calls = []

            def populate(self, *args, **kwargs):
                self.calls.append('populate')

            def _process_desired_zone(self, *args, **kwargs):
                self.calls.append('_process_desired_zone')
                return super()._process_desired_zone(*args, **kwargs)

            def _process_existing_zone(self, *args, **kwargs):
                self.calls.append('_process_existing_zone')
                return super()._process_existing_zone(*args, **kwargs)

        provider = MockProvider()

        zone = Zone('unit.tests.', [])
        self.assertFalse(provider.plan(zone))
        # ensure the calls were made in the expected order, populate comes
        # first, then desired, then existing
        self.assertEqual(['populate', '_process_desired_zone',
                          '_process_existing_zone'], provider.calls)

    def test_process_desired_zone(self):
        provider = HelperProvider('test')

        # SUPPORTS_MULTIVALUE_PTR
        provider.SUPPORTS_MULTIVALUE_PTR = False
        zone1 = Zone('unit.tests.', [])
        record1 = Record.new(zone1, 'ptr', {
            'type': 'PTR',
            'ttl': 3600,
            'values': ['foo.com.', 'bar.com.'],
        })
        zone1.add_record(record1)

        zone2 = provider._process_desired_zone(zone1.copy())
        record2 = list(zone2.records)[0]
        self.assertEqual(len(record2.values), 1)

        provider.SUPPORTS_MULTIVALUE_PTR = True
        zone2 = provider._process_desired_zone(zone1.copy())
        record2 = list(zone2.records)[0]
        self.assertEqual(len(record2.values), 2)

        # SUPPORTS_DYNAMIC
        provider.SUPPORTS_DYNAMIC = False
        zone1 = Zone('unit.tests.', [])
        record1 = Record.new(zone1, 'a', {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': '1.1.1.1',
                        }],
                    },
                },
                'rules': [{
                    'pool': 'one',
                }],
            },
            'type': 'A',
            'ttl': 3600,
            'values': ['2.2.2.2'],
        })
        self.assertTrue(record1.dynamic)
        zone1.add_record(record1)

        zone2 = provider._process_desired_zone(zone1.copy())
        record2 = list(zone2.records)[0]
        self.assertFalse(record2.dynamic)

        provider.SUPPORTS_DYNAMIC = True
        zone2 = provider._process_desired_zone(zone1.copy())
        record2 = list(zone2.records)[0]
        self.assertTrue(record2.dynamic)

        # SUPPORTS_POOL_VALUE_STATUS
        provider.SUPPORTS_POOL_VALUE_STATUS = False
        zone1 = Zone('unit.tests.', [])
        record1.dynamic.pools['one'].data['values'][0]['status'] = 'up'
        zone1.add_record(record1)

        zone2 = provider._process_desired_zone(zone1.copy())
        record2 = list(zone2.records)[0]
        self.assertEqual(
            record2.dynamic.pools['one'].data['values'][0]['status'],
            'obey'
        )

        # SUPPORTS_ROOT_NS
        provider.SUPPORTS_ROOT_NS = False
        zone1 = Zone('unit.tests.', [])
        record1 = Record.new(zone1, '', {
            'type': 'NS',
            'ttl': 3600,
            'values': ['foo.com.', 'bar.com.'],
        })
        zone1.add_record(record1)

        zone2 = provider._process_desired_zone(zone1.copy())
        self.assertEqual(0, len(zone2.records))

        provider.SUPPORTS_ROOT_NS = True
        zone2 = provider._process_desired_zone(zone1.copy())
        self.assertEqual(1, len(zone2.records))
        self.assertEqual(record1, list(zone2.records)[0])

    def test_process_existing_zone(self):
        provider = HelperProvider('test')

        # SUPPORTS_ROOT_NS
        provider.SUPPORTS_ROOT_NS = False
        zone1 = Zone('unit.tests.', [])
        record1 = Record.new(zone1, '', {
            'type': 'NS',
            'ttl': 3600,
            'values': ['foo.com.', 'bar.com.'],
        })
        zone1.add_record(record1)

        zone2 = provider._process_existing_zone(zone1.copy())
        self.assertEqual(0, len(zone2.records))

        provider.SUPPORTS_ROOT_NS = True
        zone2 = provider._process_existing_zone(zone1.copy())
        self.assertEqual(1, len(zone2.records))
        self.assertEqual(record1, list(zone2.records)[0])

    def test_safe_none(self):
        # No changes is safe
        Plan(None, None, [], True).raise_if_unsafe()

    def test_safe_creates(self):
        # Creates are safe when existing records is under MIN_EXISTING_RECORDS
        zone = Zone('unit.tests.', [])

        record = Record.new(zone, 'a', {
            'ttl': 30,
            'type': 'A',
            'value': '1.2.3.4',
        })
        Plan(zone, zone, [Create(record) for i in range(10)], True) \
            .raise_if_unsafe()

    def test_safe_min_existing_creates(self):
        # Creates are safe when existing records is over MIN_EXISTING_RECORDS
        zone = Zone('unit.tests.', [])

        record = Record.new(zone, 'a', {
            'ttl': 30,
            'type': 'A',
            'value': '1.2.3.4',
        })

        for i in range(int(Plan.MIN_EXISTING_RECORDS)):
            zone.add_record(Record.new(zone, str(i), {
                            'ttl': 60,
                            'type': 'A',
                            'value': '2.3.4.5'
                            }))

        Plan(zone, zone, [Create(record) for i in range(10)], True) \
            .raise_if_unsafe()

    def test_safe_no_existing(self):
        # existing records fewer than MIN_EXISTING_RECORDS is safe
        zone = Zone('unit.tests.', [])
        record = Record.new(zone, 'a', {
            'ttl': 30,
            'type': 'A',
            'value': '1.2.3.4',
        })

        updates = [Update(record, record), Update(record, record)]
        Plan(zone, zone, updates, True).raise_if_unsafe()

    def test_safe_updates_min_existing(self):
        # MAX_SAFE_UPDATE_PCENT+1 fails when more
        # than MIN_EXISTING_RECORDS exist
        zone = Zone('unit.tests.', [])
        record = Record.new(zone, 'a', {
            'ttl': 30,
            'type': 'A',
            'value': '1.2.3.4',
        })

        for i in range(int(Plan.MIN_EXISTING_RECORDS)):
            zone.add_record(Record.new(zone, str(i), {
                            'ttl': 60,
                            'type': 'A',
                            'value': '2.3.4.5'
                            }))

        changes = [Update(record, record)
                   for i in range(int(Plan.MIN_EXISTING_RECORDS *
                                      Plan.MAX_SAFE_UPDATE_PCENT) + 1)]

        with self.assertRaises(UnsafePlan) as ctx:
            Plan(zone, zone, changes, True).raise_if_unsafe()

        self.assertTrue('Too many updates' in str(ctx.exception))

    def test_safe_updates_min_existing_pcent(self):
        # MAX_SAFE_UPDATE_PCENT is safe when more
        # than MIN_EXISTING_RECORDS exist
        zone = Zone('unit.tests.', [])
        record = Record.new(zone, 'a', {
            'ttl': 30,
            'type': 'A',
            'value': '1.2.3.4',
        })

        for i in range(int(Plan.MIN_EXISTING_RECORDS)):
            zone.add_record(Record.new(zone, str(i), {
                            'ttl': 60,
                            'type': 'A',
                            'value': '2.3.4.5'
                            }))
        changes = [Update(record, record)
                   for i in range(int(Plan.MIN_EXISTING_RECORDS *
                                      Plan.MAX_SAFE_UPDATE_PCENT))]

        Plan(zone, zone, changes, True).raise_if_unsafe()

    def test_safe_deletes_min_existing(self):
        # MAX_SAFE_DELETE_PCENT+1 fails when more
        # than MIN_EXISTING_RECORDS exist
        zone = Zone('unit.tests.', [])
        record = Record.new(zone, 'a', {
            'ttl': 30,
            'type': 'A',
            'value': '1.2.3.4',
        })

        for i in range(int(Plan.MIN_EXISTING_RECORDS)):
            zone.add_record(Record.new(zone, str(i), {
                            'ttl': 60,
                            'type': 'A',
                            'value': '2.3.4.5'
                            }))

        changes = [Delete(record)
                   for i in range(int(Plan.MIN_EXISTING_RECORDS *
                                      Plan.MAX_SAFE_DELETE_PCENT) + 1)]

        with self.assertRaises(UnsafePlan) as ctx:
            Plan(zone, zone, changes, True).raise_if_unsafe()

        self.assertTrue('Too many deletes' in str(ctx.exception))

    def test_safe_deletes_min_existing_pcent(self):
        # MAX_SAFE_DELETE_PCENT is safe when more
        # than MIN_EXISTING_RECORDS exist
        zone = Zone('unit.tests.', [])
        record = Record.new(zone, 'a', {
            'ttl': 30,
            'type': 'A',
            'value': '1.2.3.4',
        })

        for i in range(int(Plan.MIN_EXISTING_RECORDS)):
            zone.add_record(Record.new(zone, str(i), {
                            'ttl': 60,
                            'type': 'A',
                            'value': '2.3.4.5'
                            }))
        changes = [Delete(record)
                   for i in range(int(Plan.MIN_EXISTING_RECORDS *
                                      Plan.MAX_SAFE_DELETE_PCENT))]

        Plan(zone, zone, changes, True).raise_if_unsafe()

    def test_safe_updates_min_existing_override(self):
        safe_pcent = .4
        # 40% + 1 fails when more
        # than MIN_EXISTING_RECORDS exist
        zone = Zone('unit.tests.', [])
        record = Record.new(zone, 'a', {
            'ttl': 30,
            'type': 'A',
            'value': '1.2.3.4',
        })

        for i in range(int(Plan.MIN_EXISTING_RECORDS)):
            zone.add_record(Record.new(zone, str(i), {
                            'ttl': 60,
                            'type': 'A',
                            'value': '2.3.4.5'
                            }))

        changes = [Update(record, record)
                   for i in range(int(Plan.MIN_EXISTING_RECORDS *
                                      safe_pcent) + 1)]

        with self.assertRaises(UnsafePlan) as ctx:
            Plan(zone, zone, changes, True,
                 update_pcent_threshold=safe_pcent).raise_if_unsafe()

        self.assertTrue('Too many updates' in str(ctx.exception))

    def test_safe_deletes_min_existing_override(self):
        safe_pcent = .4
        # 40% + 1 fails when more
        # than MIN_EXISTING_RECORDS exist
        zone = Zone('unit.tests.', [])
        record = Record.new(zone, 'a', {
            'ttl': 30,
            'type': 'A',
            'value': '1.2.3.4',
        })

        for i in range(int(Plan.MIN_EXISTING_RECORDS)):
            zone.add_record(Record.new(zone, str(i), {
                            'ttl': 60,
                            'type': 'A',
                            'value': '2.3.4.5'
                            }))

        changes = [Delete(record)
                   for i in range(int(Plan.MIN_EXISTING_RECORDS *
                                      safe_pcent) + 1)]

        with self.assertRaises(UnsafePlan) as ctx:
            Plan(zone, zone, changes, True,
                 delete_pcent_threshold=safe_pcent).raise_if_unsafe()

        self.assertTrue('Too many deletes' in str(ctx.exception))

    def test_supports_warn_or_except(self):
        class MinimalProvider(BaseProvider):
            SUPPORTS = set()
            SUPPORTS_GEO = False

            def __init__(self, **kwargs):
                self.log = MagicMock()
                super(MinimalProvider, self).__init__('minimal', **kwargs)

        normal = MinimalProvider(strict_supports=False)
        # Should log and not expect
        normal.supports_warn_or_except('Hello World!', 'Goodbye')
        normal.log.warning.assert_called_once()
        normal.log.warning.assert_has_calls([
            call('%s; %s', 'Hello World!', 'Goodbye')
        ])

        strict = MinimalProvider(strict_supports=True)
        # Should log and not expect
        with self.assertRaises(SupportsException) as ctx:
            strict.supports_warn_or_except('Hello World!', 'Will not see')
        self.assertEqual('minimal: Hello World!', str(ctx.exception))
        strict.log.warning.assert_not_called()


class TestBaseProviderSupportsRootNs(TestCase):

    class Provider(BaseProvider):
        log = getLogger('Provider')

        SUPPORTS = set(('A', 'NS'))
        SUPPORTS_GEO = False
        SUPPORTS_ROOT_NS = False

        strict_supports = False

        def __init__(self, existing=None):
            super().__init__('test')
            self.existing = existing

        def populate(self, zone, target=False, lenient=False):
            if self.existing:
                for record in self.existing.records:
                    zone.add_record(record)
                return True
            return False

    zone = Zone('unit.tests.', [])
    a_record = Record.new(zone, 'ptr', {
        'type': 'A',
        'ttl': 3600,
        'values': ['1.2.3.4', '2.3.4.5'],
    })
    ns_record = Record.new(zone, 'sub', {
        'type': 'NS',
        'ttl': 3600,
        'values': ['ns2.foo.com.', 'ns2.bar.com.'],
    })
    no_root = zone.copy()
    no_root.add_record(a_record)
    no_root.add_record(ns_record)

    root_ns_record = Record.new(zone, '', {
        'type': 'NS',
        'ttl': 3600,
        'values': ['ns1.foo.com.', 'ns1.bar.com.'],
    })
    has_root = no_root.copy()
    has_root.add_record(root_ns_record)

    other_root_ns_record = Record.new(zone, '', {
        'type': 'NS',
        'ttl': 3600,
        'values': ['ns4.foo.com.', 'ns4.bar.com.'],
    })
    different_root = no_root.copy()
    different_root.add_record(other_root_ns_record)

    # False

    def test_supports_root_ns_false_matches(self):
        # provider has a matching existing root record
        provider = self.Provider(self.has_root)
        provider.SUPPORTS_ROOT_NS = False

        # matching root NS in the desired
        plan = provider.plan(self.has_root)
        # there's an existing root record that matches the desired. we don't
        # support them, so it doesn't matter whether it matches or not.
        # _process_desired_zone will have removed the desired one since it
        # can't be managed. this will not result in a plan as
        # _process_existing_zone will have done so as well.
        self.assertFalse(plan)

    def test_supports_root_ns_false_different(self):
        # provider has a non-matching existing record
        provider = self.Provider(self.different_root)
        provider.SUPPORTS_ROOT_NS = False

        # different root is in the desired
        plan = provider.plan(self.has_root)
        # the mis-match doesn't matter since we can't manage the records
        # anyway, they will have been removed from the desired and existing.
        self.assertFalse(plan)

    def test_supports_root_ns_false_missing(self):
        # provider has an existing record
        provider = self.Provider(self.has_root)
        provider.SUPPORTS_ROOT_NS = False

        # desired doesn't have a root
        plan = provider.plan(self.no_root)
        # the mis-match doesn't matter since we can't manage the records
        # anyway, they will have been removed from the desired and existing.
        self.assertFalse(plan)

    def test_supports_root_ns_false_create_zone(self):
        # provider has no existing records (create)
        provider = self.Provider()
        provider.SUPPORTS_ROOT_NS = False
        # case where we have a root NS in the desired
        plan = provider.plan(self.has_root)
        # there's no existing root record since we're creating the zone so
        # we'll get a plan that creates the other 2 records only
        self.assertTrue(plan)
        self.assertEqual(2, len(plan.changes))

    # True

    def test_supports_root_ns_true_matches(self):
        # provider has a matching existing root record
        provider = self.Provider(self.has_root)
        provider.SUPPORTS_ROOT_NS = True
        # case where we have a root NS in the desired
        plan = provider.plan(self.has_root)
        # there's an existing root record that matches the desired state so no
        # changes are needed
        self.assertFalse(plan)

    def test_supports_root_ns_true_different(self):
        # provider has a non-matching existing record
        provider = self.Provider(self.different_root)
        provider.SUPPORTS_ROOT_NS = True
        # case where we have a root NS in the desired
        plan = provider.plan(self.has_root)
        # there's an existing root record that doesn't match the desired state.
        # we'll get a plan that modifies it.
        self.assertTrue(plan)
        change = plan.changes[0]
        self.assertEqual(self.other_root_ns_record, change.existing)
        self.assertEqual(self.root_ns_record, change.new)

    # TODO: rework
    def _test_supports_root_ns_true_missing(self):
        # provider has a matching existing root record
        provider = self.Provider(self.has_root)
        provider.SUPPORTS_ROOT_NS = True
        # case where we don't have a configured/desired root NS record. this is
        # dangerous so we expect an exception to be thrown to prevent trying to
        # delete the critical record
        with self.assertRaises(SupportsException) as ctx:
            provider.plan(self.no_root)
        self.assertEqual('test: provider supports root NS record management, '
                         'but no record configured in unit.tests.; aborting',
                         str(ctx.exception))

    def test_supports_root_ns_true_create_zone(self):
        # provider has no existing records (create)
        provider = self.Provider()
        provider.SUPPORTS_ROOT_NS = True
        # case where we have a root NS in the desired
        plan = provider.plan(self.has_root)
        # there's no existing root record since we're creating the zone so
        # we'll get a plan that creates everything, including it
        self.assertTrue(plan)
        self.assertEqual(3, len(plan.changes))
        change = [c for c in plan.changes
                  if c.new.name == '' and c.new._type == 'NS'][0]
        self.assertFalse(change.existing)
        self.assertEqual(self.root_ns_record, change.new)

    # TODO: rework
    def _test_supports_root_ns_true_create_zone_missing(self):
        # provider has no existing records (create)
        provider = self.Provider()
        provider.SUPPORTS_ROOT_NS = True
        # case where we don't have a configured/desired root NS record. this is
        # dangerous so we expect an exception to be thrown to prevent trying to
        # create a zone without the critical record being managed (if they
        # didn't get it now they'd get it on the next sync)
        with self.assertRaises(SupportsException) as ctx:
            provider.plan(self.no_root)
        self.assertEqual('test: provider supports root NS record management, '
                         'but no record configured in unit.tests.; aborting',
                         str(ctx.exception))
