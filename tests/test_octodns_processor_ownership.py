#
#
#

from unittest import TestCase

from helpers import PlannableProvider

from octodns.processor.ownership import OwnershipProcessor
from octodns.provider.plan import Plan
from octodns.record import Delete, Record
from octodns.zone import Zone

zone = Zone('unit.tests.', [])
records = {}
for record in [
    Record.new(
        zone, '', {'ttl': 30, 'type': 'A', 'values': ['1.2.3.4', '5.6.7.8']}
    ),
    Record.new(zone, 'the-a', {'ttl': 30, 'type': 'A', 'value': '1.2.3.4'}),
    Record.new(zone, 'the-aaaa', {'ttl': 30, 'type': 'AAAA', 'value': '::1'}),
    Record.new(
        zone, 'the-txt', {'ttl': 30, 'type': 'TXT', 'value': 'Hello World!'}
    ),
    Record.new(zone, '*', {'ttl': 30, 'type': 'A', 'value': '4.3.2.1'}),
]:
    records[record.name] = record
    zone.add_record(record)


class TestOwnershipProcessor(TestCase):
    def test_process_source_zone(self):
        ownership = OwnershipProcessor('ownership')

        got = ownership.process_source_zone(zone.copy())
        self.assertEqual(
            [
                '',
                '*',
                '_owner.a',
                '_owner.a._wildcard',
                '_owner.a.the-a',
                '_owner.aaaa.the-aaaa',
                '_owner.txt.the-txt',
                'the-a',
                'the-aaaa',
                'the-txt',
            ],
            sorted([r.name for r in got.records]),
        )

        found = False
        for record in got.records:
            if record.name.startswith(ownership.txt_name):
                self.assertEqual([ownership.txt_value], record.values)
                # test _is_ownership while we're in here
                self.assertTrue(ownership._is_ownership(record))
                found = True
            else:
                self.assertFalse(ownership._is_ownership(record))
        self.assertTrue(found)

    def test_process_plan(self):
        ownership = OwnershipProcessor('ownership')
        provider = PlannableProvider('helper')

        # No plan, is a quick noop
        self.assertFalse(ownership.process_plan(None))

        # Nothing exists create both records and ownership
        ownership_added = ownership.process_source_zone(zone.copy())
        plan = provider.plan(ownership_added)
        self.assertTrue(plan)
        # Double the number of records
        self.assertEqual(len(records) * 2, len(plan.changes))
        # Now process the plan, shouldn't make any changes, we're creating
        # everything
        got = ownership.process_plan(plan)
        self.assertTrue(got)
        self.assertEqual(len(records) * 2, len(got.changes))

        # Something extra exists and doesn't have ownership TXT, leave it
        # alone, we don't own it.
        extra_a = Record.new(
            zone, 'extra-a', {'ttl': 30, 'type': 'A', 'value': '4.4.4.4'}
        )
        plan.existing.add_record(extra_a)
        # If we'd done a "real" plan we'd have a delete for the extra thing.
        plan.changes.append(Delete(extra_a))
        # Process the plan, shouldn't make any changes since the extra bit is
        # something we don't own
        got = ownership.process_plan(plan)
        self.assertTrue(got)
        self.assertEqual(len(records) * 2, len(got.changes))

        # Something extra exists and does have an ownership record so we will
        # delete it...
        copy = Zone('unit.tests.', [])
        for record in records.values():
            if record.name != 'the-a':
                copy.add_record(record)
        # New ownership, without the `the-a`
        ownership_added = ownership.process_source_zone(copy)
        self.assertEqual(len(records) * 2 - 2, len(ownership_added.records))
        plan = provider.plan(ownership_added)
        # Fake the extra existing by adding the record, its ownership, and the
        # two delete changes.
        the_a = records['the-a']
        plan.existing.add_record(the_a)
        name = f'{ownership.txt_name}.a.the-a'
        the_a_ownership = Record.new(
            zone, name, {'ttl': 30, 'type': 'TXT', 'value': ownership.txt_value}
        )
        plan.existing.add_record(the_a_ownership)
        plan.changes.append(Delete(the_a))
        plan.changes.append(Delete(the_a_ownership))
        # Finally process the plan, should be a noop and we should get the same
        # plan out, meaning the planned deletes were allowed to happen.
        got = ownership.process_plan(plan)
        self.assertTrue(got)
        self.assertEqual(plan, got)
        self.assertEqual(len(plan.changes), len(got.changes))

    def test_remove_last_change(self):
        ownership = OwnershipProcessor('ownership')

        record = Record.new(
            zone, 'a', {'ttl': 30, 'type': 'A', 'value': '4.4.4.4'}
        )

        existing = Zone('unit.tests.', [])
        existing.add_record(record)
        desired = Zone('unit.tests.', [])

        change = Delete(record)

        plan = Plan(
            existing=existing, desired=desired, changes=[change], exists=True
        )
        self.assertEqual(1, len(plan.changes))
        plan = ownership.process_plan(plan)
        self.assertFalse(plan)
