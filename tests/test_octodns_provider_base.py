#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger
from mock import MagicMock, call
from unittest import TestCase

from octodns.processor.base import BaseProcessor
from octodns.provider import SupportsException
from octodns.provider.base import BaseProvider
from octodns.provider.plan import Plan, UnsafePlan
from octodns.record import Create, Delete, Record, Update
from octodns.zone import Zone


class HelperProvider(BaseProvider):
    log = getLogger('HelperProvider')

    SUPPORTS = set(('A', 'PTR'))
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
        pass

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
        self.assertEquals('Abstract base class, log property missing',
                          str(ctx.exception))

        class HasLog(BaseProvider):
            log = getLogger('HasLog')

        with self.assertRaises(NotImplementedError) as ctx:
            HasLog('haslog')
        self.assertEquals('Abstract base class, SUPPORTS_GEO property missing',
                          str(ctx.exception))

        class HasSupportsGeo(HasLog):
            SUPPORTS_GEO = False

        zone = Zone('unit.tests.', ['sub'])
        with self.assertRaises(NotImplementedError) as ctx:
            HasSupportsGeo('hassupportsgeo').populate(zone)
        self.assertEquals('Abstract base class, SUPPORTS property missing',
                          str(ctx.exception))

        class HasSupports(HasSupportsGeo):
            SUPPORTS = set(('A',))
        with self.assertRaises(NotImplementedError) as ctx:
            HasSupports('hassupports').populate(zone)
        self.assertEquals('Abstract base class, populate method missing',
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
        self.assertEquals(3, len(plan.changes))

        with self.assertRaises(NotImplementedError) as ctx:
            HasPopulate('haspopulate').apply(plan)
        self.assertEquals('Abstract base class, _apply method missing',
                          str(ctx.exception))

    def test_plan(self):
        ignored = Zone('unit.tests.', [])

        # No change, thus no plan
        provider = HelperProvider([])
        self.assertEquals(None, provider.plan(ignored))

        record = Record.new(ignored, 'a', {
            'ttl': 30,
            'type': 'A',
            'value': '1.2.3.4',
        })
        provider = HelperProvider([Create(record)])
        plan = provider.plan(ignored)
        self.assertTrue(plan)
        self.assertEquals(1, len(plan.changes))

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
        self.assertEquals(1, len(plan.changes))
        self.assertIsInstance(plan.changes[0], Delete)
        # Called processor stored its params
        self.assertTrue(tricky.existing)
        self.assertEquals(zone.name, tricky.existing.name)

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
        self.assertEquals(2, len(plan.changes))
        self.assertIsInstance(plan.changes[0], Delete)
        self.assertIsInstance(plan.changes[1], Delete)
        # 2nd processor stored its params, and we'll see the record the
        # first one added
        self.assertTrue(another.existing)
        self.assertEquals(zone.name, another.existing.name)
        self.assertEquals(1, len(another.existing.records))

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
        self.assertEquals(1, provider.apply(plan))

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

    def test_check_dynamic_for_private_ips(self):
        provider = HelperProvider('test')

        # CNAME is a no-op
        zone = Zone('unit.tests.', [])
        record = Record.new(zone, 'cname', {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            'value': 'foo.unit.tests.',
                        }],
                    },
                },
                'rules': [{
                    'pool': 'one',
                }],
            },
            'type': 'CNAME',
            'ttl': 3600,
            'value': 'bar.unit.tests.',
        })
        provider._check_dynamic_for_private_ips(zone, record)
        # Nothing modified
        self.assertEquals(0, len(zone.records))

        # A with a mixture of IPs
        zone = Zone('unit.tests.', [])
        data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            # routable
                            'value': '1.1.1.1',
                        }, {
                            # RFC5737
                            'value': '192.0.2.43',
                        }, {
                            # RFC1918
                            'value': '192.168.1.42',
                        }],
                    },
                },
                'rules': [{
                    'pool': 'one',
                }],
            },
            'type': 'A',
            'ttl': 3600,
            'value': '2.2.2.2',
        }
        record = Record.new(zone, 'a', data)
        provider._check_dynamic_for_private_ips(zone, record)
        # Record will have been modified
        self.assertEquals(1, len(zone.records))
        got = list(zone.records)[0].data['dynamic']['pools']['one']['values']
        # Record data has been updated
        expected = data['dynamic']['pools']['one']['values']
        expected[0].update({'status': 'obey', 'weight': 1})
        expected[1].update({'status': 'up', 'weight': 1})
        expected[2].update({'status': 'up', 'weight': 1})
        self.assertEquals(expected, got)

        # AAAA with a mixture of IPs
        zone = Zone('unit.tests.', [])
        data = {
            'dynamic': {
                'pools': {
                    'one': {
                        'values': [{
                            # routable
                            'value': '2607:f8b0:400a:803::200d',
                        }, {
                            # non
                            'value': 'fc00::1'
                        }],
                    },
                },
                'rules': [{
                    'pool': 'one',
                }],
            },
            'type': 'AAAA',
            'ttl': 3600,
            'value': '2607:f8b0:400a:803::200e',
        }
        record = Record.new(zone, 'aaaa', data)
        provider._check_dynamic_for_private_ips(zone, record)
        # Record will have been modified
        self.assertEquals(1, len(zone.records))
        got = list(zone.records)[0].data['dynamic']['pools']['one']['values']
        # Record data has been updated
        expected = data['dynamic']['pools']['one']['values']
        expected[0].update({'status': 'obey', 'weight': 1})
        expected[1].update({'status': 'up', 'weight': 1})
        self.assertEquals(expected, got)

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
        self.assertEquals('minimal: Hello World!', str(ctx.exception))
        strict.log.warning.assert_not_called()
