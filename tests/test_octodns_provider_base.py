#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger
from unittest import TestCase

from octodns.record import Create, Delete, Record, Update
from octodns.provider.base import BaseProvider, Plan, UnsafePlan
from octodns.zone import Zone


class HelperProvider(BaseProvider):
    log = getLogger('HelperProvider')

    def __init__(self, extra_changes, apply_disabled=False,
                 include_change_callback=None):
        self.__extra_changes = extra_changes
        self.apply_disabled = apply_disabled
        self.include_change_callback = include_change_callback

    def populate(self, zone, target=False):
        pass

    def _include_change(self, change):
        return not self.include_change_callback or \
            self.include_change_callback(change)

    def _extra_changes(self, existing, changes):
        return self.__extra_changes

    def _apply(self, plan):
        pass


class TestBaseProvider(TestCase):

    def test_base_provider(self):
        with self.assertRaises(NotImplementedError) as ctx:
            BaseProvider('base')
        self.assertEquals('Abstract base class, log property missing',
                          ctx.exception.message)

        class HasLog(BaseProvider):
            log = getLogger('HasLog')

        with self.assertRaises(NotImplementedError) as ctx:
            HasLog('haslog')
        self.assertEquals('Abstract base class, SUPPORTS_GEO property missing',
                          ctx.exception.message)

        class HasSupportsGeo(HasLog):
            SUPPORTS_GEO = False

        zone = Zone('unit.tests.', [])
        with self.assertRaises(NotImplementedError) as ctx:
            HasSupportsGeo('hassupportesgeo').populate(zone)
        self.assertEquals('Abstract base class, populate method missing',
                          ctx.exception.message)

        class HasPopulate(HasSupportsGeo):

            def populate(self, zone, target=False):
                zone.add_record(Record.new(zone, '', {
                    'ttl': 60,
                    'type': 'A',
                    'value': '2.3.4.5'
                }))
                zone.add_record(Record.new(zone, 'going', {
                    'ttl': 60,
                    'type': 'A',
                    'value': '3.4.5.6'
                }))

        zone.add_record(Record.new(zone, '', {
            'ttl': 60,
            'type': 'A',
            'value': '1.2.3.4'
        }))

        self.assertTrue(HasSupportsGeo('hassupportesgeo')
                        .supports(list(zone.records)[0]))

        plan = HasPopulate('haspopulate').plan(zone)
        self.assertEquals(2, len(plan.changes))

        with self.assertRaises(NotImplementedError) as ctx:
            HasPopulate('haspopulate').apply(plan)
        self.assertEquals('Abstract base class, _apply method missing',
                          ctx.exception.message)

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

    def test_safe(self):
        ignored = Zone('unit.tests.', [])

        # No changes is safe
        Plan(None, None, []).raise_if_unsafe()

        # Creates are safe
        record = Record.new(ignored, 'a', {
            'ttl': 30,
            'type': 'A',
            'value': '1.2.3.4',
        })
        Plan(None, None, [Create(record) for i in range(10)]).raise_if_unsafe()

        # max Updates is safe
        changes = [Update(record, record)
                   for i in range(Plan.MAX_SAFE_UPDATES)]
        Plan(None, None, changes).raise_if_unsafe()
        # but max + 1 isn't
        with self.assertRaises(UnsafePlan):
            changes.append(Update(record, record))
            Plan(None, None, changes).raise_if_unsafe()

        # max Deletes is safe
        changes = [Delete(record) for i in range(Plan.MAX_SAFE_DELETES)]
        Plan(None, None, changes).raise_if_unsafe()
        # but max + 1 isn't
        with self.assertRaises(UnsafePlan):
            changes.append(Delete(record))
            Plan(None, None, changes).raise_if_unsafe()
