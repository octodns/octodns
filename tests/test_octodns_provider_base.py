#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger
from six import text_type
from unittest import TestCase

from octodns.record import Create, Delete, Record, Update
from octodns.provider.base import BaseProvider
from octodns.provider.plan import Plan, UnsafePlan
from octodns.zone import Zone


class HelperProvider(BaseProvider):
    log = getLogger('HelperProvider')

    SUPPORTS = set(('A',))
    id = 'test'

    def __init__(self, extra_changes, apply_disabled=False,
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


class TestBaseProvider(TestCase):

    def test_base_provider(self):
        with self.assertRaises(NotImplementedError) as ctx:
            BaseProvider('base')
        self.assertEquals('Abstract base class, log property missing',
                          text_type(ctx.exception))

        class HasLog(BaseProvider):
            log = getLogger('HasLog')

        with self.assertRaises(NotImplementedError) as ctx:
            HasLog('haslog')
        self.assertEquals('Abstract base class, SUPPORTS_GEO property missing',
                          text_type(ctx.exception))

        class HasSupportsGeo(HasLog):
            SUPPORTS_GEO = False

        zone = Zone('unit.tests.', ['sub'])
        with self.assertRaises(NotImplementedError) as ctx:
            HasSupportsGeo('hassupportsgeo').populate(zone)
        self.assertEquals('Abstract base class, SUPPORTS property missing',
                          text_type(ctx.exception))

        class HasSupports(HasSupportsGeo):
            SUPPORTS = set(('A',))
        with self.assertRaises(NotImplementedError) as ctx:
            HasSupports('hassupports').populate(zone)
        self.assertEquals('Abstract base class, populate method missing',
                          text_type(ctx.exception))

        # SUPPORTS_DYNAMIC has a default/fallback
        self.assertFalse(HasSupports('hassupports').SUPPORTS_DYNAMIC)

        # But can be overridden
        class HasSupportsDyanmic(HasSupports):
            SUPPORTS_DYNAMIC = True

        self.assertTrue(HasSupportsDyanmic('hassupportsdynamic')
                        .SUPPORTS_DYNAMIC)

        self.assertFalse(HasSupports('hassupports').SUPPORTS_ROOT_NS)

        class HasSupportsRootNS(HasSupports):
            SUPPORTS_ROOT_NS = True

        self.assertTrue(HasSupportsRootNS('hassupportsrootns')
                        .SUPPORTS_ROOT_NS)

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
                          text_type(ctx.exception))

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
            zone.add_record(Record.new(zone, text_type(i), {
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
            zone.add_record(Record.new(zone, text_type(i), {
                            'ttl': 60,
                            'type': 'A',
                            'value': '2.3.4.5'
                            }))

        changes = [Update(record, record)
                   for i in range(int(Plan.MIN_EXISTING_RECORDS *
                                      Plan.MAX_SAFE_UPDATE_PCENT) + 1)]

        with self.assertRaises(UnsafePlan) as ctx:
            Plan(zone, zone, changes, True).raise_if_unsafe()

        self.assertTrue('Too many updates' in text_type(ctx.exception))

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
            zone.add_record(Record.new(zone, text_type(i), {
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
            zone.add_record(Record.new(zone, text_type(i), {
                            'ttl': 60,
                            'type': 'A',
                            'value': '2.3.4.5'
                            }))

        changes = [Delete(record)
                   for i in range(int(Plan.MIN_EXISTING_RECORDS *
                                      Plan.MAX_SAFE_DELETE_PCENT) + 1)]

        with self.assertRaises(UnsafePlan) as ctx:
            Plan(zone, zone, changes, True).raise_if_unsafe()

        self.assertTrue('Too many deletes' in text_type(ctx.exception))

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
            zone.add_record(Record.new(zone, text_type(i), {
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
            zone.add_record(Record.new(zone, text_type(i), {
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

        self.assertTrue('Too many updates' in text_type(ctx.exception))

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
            zone.add_record(Record.new(zone, text_type(i), {
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

        self.assertTrue('Too many deletes' in text_type(ctx.exception))
