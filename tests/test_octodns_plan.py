#
#
#

from io import StringIO
from logging import getLogger
from unittest import TestCase

from helpers import SimpleProvider

from octodns.provider.plan import (
    Plan,
    PlanHtml,
    PlanLogger,
    PlanMarkdown,
    RootNsChange,
    TooMuchChange,
)
from octodns.record import Create, Delete, Record, Update
from octodns.zone import Zone

simple = SimpleProvider()
zone = Zone('unit.tests.', [])
existing = Record.new(
    zone,
    'a',
    {
        'ttl': 300,
        'type': 'A',
        # This matches the zone data above, one to swap, one to leave
        'values': ['1.1.1.1', '2.2.2.2'],
    },
)
new = Record.new(
    zone,
    'a',
    {
        'geo': {'AF': ['5.5.5.5'], 'NA-US': ['6.6.6.6']},
        'ttl': 300,
        'type': 'A',
        # This leaves one, swaps ones, and adds one
        'values': ['2.2.2.2', '3.3.3.3', '4.4.4.4'],
    },
    simple,
)
create = Create(
    Record.new(
        zone,
        'b',
        {'ttl': 60, 'type': 'CNAME', 'value': 'foo.unit.tests.'},
        simple,
    )
)
create2 = Create(
    Record.new(
        zone, 'c', {'ttl': 60, 'type': 'CNAME', 'value': 'foo.unit.tests.'}
    )
)
update = Update(existing, new)
delete = Delete(new)
changes = [create, create2, delete, update]
plans = [
    (simple, Plan(zone, zone, changes, True)),
    (simple, Plan(zone, zone, changes, False)),
]


class TestPlanSortsChanges(TestCase):
    def test_plan_sorts_changes_pass_to_it(self):
        # we aren't worried about the details of the sorting, that's tested in
        # test_octodns_record's TestChanges. We just want to make sure that the
        # changes are sorted at all.
        zone = Zone('unit.tests.', [])
        record_a_1 = Record.new(
            zone, '1', {'type': 'A', 'ttl': 30, 'value': '1.2.3.4'}
        )
        create_a_1 = Create(record_a_1)
        record_a_2 = Record.new(
            zone, '2', {'type': 'A', 'ttl': 30, 'value': '1.2.3.4'}
        )
        create_a_2 = Create(record_a_2)

        # passed in reverse of expected order
        plan = Plan(None, None, [create_a_2, create_a_1], False)
        self.assertEqual([create_a_1, create_a_2], plan.changes)


class TestPlanLogger(TestCase):
    def test_invalid_level(self):
        with self.assertRaises(Exception) as ctx:
            PlanLogger('invalid', 'not-a-level')
        self.assertEqual('Unsupported level: not-a-level', str(ctx.exception))

    def test_create(self):
        class MockLogger(object):
            def __init__(self):
                self.out = StringIO()

            def log(self, level, msg):
                self.out.write(msg)

        log = MockLogger()
        PlanLogger('logger').run(log, plans)
        out = log.out.getvalue()
        self.assertTrue(
            'Summary: Creates=2, Updates=1, '
            'Deletes=1, Existing Records=0' in out
        )


class TestPlanHtml(TestCase):
    log = getLogger('TestPlanHtml')

    def test_empty(self):
        out = StringIO()
        PlanHtml('html').run([], fh=out)
        self.assertEqual('<b>No changes were planned</b>', out.getvalue())

    def test_simple(self):
        out = StringIO()
        PlanHtml('html').run(plans, fh=out)
        out = out.getvalue()
        self.assertTrue(
            '    <td colspan=6>Summary: Creates=2, Updates=1, '
            'Deletes=1, Existing Records=0</td>' in out
        )


class TestPlanMarkdown(TestCase):
    log = getLogger('TestPlanMarkdown')

    def test_empty(self):
        out = StringIO()
        PlanMarkdown('markdown').run([], fh=out)
        self.assertEqual('## No changes were planned\n', out.getvalue())

    def test_simple(self):
        out = StringIO()
        PlanMarkdown('markdown').run(plans, fh=out)
        out = out.getvalue()
        self.assertTrue('## unit.tests.' in out)
        self.assertTrue('Create | b | CNAME | 60 | foo.unit.tests.' in out)
        self.assertTrue('Update | a | A | 300 | 1.1.1.1;' in out)
        self.assertTrue('NA-US: 6.6.6.6 | test' in out)
        self.assertTrue('Delete | a | A | 300 | 2.2.2.2;' in out)


class HelperPlan(Plan):
    def __init__(self, *args, min_existing=0, **kwargs):
        super().__init__(*args, **kwargs)
        self.MIN_EXISTING_RECORDS = min_existing


class TestPlanSafety(TestCase):
    existing = Zone('unit.tests.', [])
    record_1 = Record.new(
        existing, '1', data={'type': 'A', 'ttl': 42, 'value': '1.2.3.4'}
    )
    record_2 = Record.new(
        existing, '2', data={'type': 'A', 'ttl': 42, 'value': '1.2.3.4'}
    )
    record_3 = Record.new(
        existing, '3', data={'type': 'A', 'ttl': 42, 'value': '1.2.3.4'}
    )
    record_4 = Record.new(
        existing, '4', data={'type': 'A', 'ttl': 42, 'value': '1.2.3.4'}
    )

    def test_too_many_updates(self):
        existing = self.existing.copy()
        changes = []

        # No records, no changes, we're good
        plan = HelperPlan(existing, None, changes, True)
        plan.raise_if_unsafe()

        # Four records, no changes, we're good
        existing.add_record(self.record_1)
        existing.add_record(self.record_2)
        existing.add_record(self.record_3)
        existing.add_record(self.record_4)
        plan = HelperPlan(existing, None, changes, True)
        plan.raise_if_unsafe()

        # Creates don't count against us
        changes.append(Create(self.record_1))
        changes.append(Create(self.record_2))
        changes.append(Create(self.record_3))
        changes.append(Create(self.record_4))
        plan = HelperPlan(existing, None, changes, True)
        plan.raise_if_unsafe()

        # One update, still good (25%, default threshold is 33%)
        changes.append(Update(self.record_1, self.record_1))
        plan = HelperPlan(existing, None, changes, True)
        plan.raise_if_unsafe()

        # Two and we're over the threshold
        changes.append(Update(self.record_2, self.record_2))
        plan = HelperPlan(existing, None, changes, True)
        with self.assertRaises(TooMuchChange) as ctx:
            plan.raise_if_unsafe()
        self.assertTrue('Too many updates', str(ctx.exception))

        # If we require more records before applying we're still OK though
        plan = HelperPlan(existing, None, changes, True, min_existing=10)
        plan.raise_if_unsafe()

    def test_too_many_deletes(self):
        existing = self.existing.copy()
        changes = []

        # No records, no changes, we're good
        plan = HelperPlan(existing, None, changes, True)
        plan.raise_if_unsafe()

        # Four records, no changes, we're good
        existing.add_record(self.record_1)
        existing.add_record(self.record_2)
        existing.add_record(self.record_3)
        existing.add_record(self.record_4)
        plan = HelperPlan(existing, None, changes, True)
        plan.raise_if_unsafe()

        # Creates don't count against us
        changes.append(Create(self.record_1))
        changes.append(Create(self.record_2))
        changes.append(Create(self.record_3))
        changes.append(Create(self.record_4))
        plan = HelperPlan(existing, None, changes, True)
        plan.raise_if_unsafe()

        # One delete, still good (25%, default threshold is 33%)
        changes.append(Delete(self.record_1))
        plan = HelperPlan(existing, None, changes, True)
        plan.raise_if_unsafe()

        # Two and we're over the threshold
        changes.append(Delete(self.record_2))
        plan = HelperPlan(existing, None, changes, True)
        with self.assertRaises(TooMuchChange) as ctx:
            plan.raise_if_unsafe()
        self.assertTrue('Too many deletes', str(ctx.exception))

        # If we require more records before applying we're still OK though
        plan = HelperPlan(existing, None, changes, True, min_existing=10)
        plan.raise_if_unsafe()

    def test_root_ns_change(self):
        existing = self.existing.copy()
        changes = []

        # No records, no changes, we're good
        plan = HelperPlan(existing, None, changes, True)
        plan.raise_if_unsafe()

        existing.add_record(self.record_1)
        existing.add_record(self.record_2)
        existing.add_record(self.record_3)
        existing.add_record(self.record_4)

        # Non NS changes and we're still good
        changes.append(Update(self.record_1, self.record_1))
        plan = HelperPlan(existing, None, changes, True)
        plan.raise_if_unsafe()

        # Add a change to a non-root NS record, we're OK
        ns_record = Record.new(
            existing,
            'sub',
            data={
                'type': 'NS',
                'ttl': 43,
                'values': ('ns1.unit.tests.', 'ns1.unit.tests.'),
            },
        )
        changes.append(Delete(ns_record))
        plan = HelperPlan(existing, None, changes, True)
        plan.raise_if_unsafe()
        # Remove that Delete so that we don't go over the delete threshold
        changes.pop(-1)

        # Delete the root NS record and we get an unsafe
        root_ns_record = Record.new(
            existing,
            '',
            data={
                'type': 'NS',
                'ttl': 43,
                'values': ('ns3.unit.tests.', 'ns4.unit.tests.'),
            },
        )
        changes.append(Delete(root_ns_record))
        plan = HelperPlan(existing, None, changes, True)
        with self.assertRaises(RootNsChange) as ctx:
            plan.raise_if_unsafe()
        self.assertTrue('Root Ns record change', str(ctx.exception))

    def test_data(self):
        data = plans[0][1].data
        # plans should have a single key, changes
        self.assertEqual(('changes',), tuple(data.keys()))
        # it should be a list
        self.assertIsInstance(data['changes'], list)
        # w/4 elements
        self.assertEqual(4, len(data['changes']))

        # we'll test the change .data's here while we're at it since they don't
        # have a dedicated test (file)
        delete_data = data['changes'][0]  # delete
        self.assertEqual(['existing', 'type'], sorted(delete_data.keys()))
        self.assertEqual('delete', delete_data['type'])
        self.assertEqual(delete.existing.data, delete_data['existing'])

        create_data = data['changes'][1]  # create
        self.assertEqual(['new', 'type'], sorted(create_data.keys()))
        self.assertEqual('create', create_data['type'])
        self.assertEqual(create.new.data, create_data['new'])

        update_data = data['changes'][3]  # update
        self.assertEqual(
            ['existing', 'new', 'type'], sorted(update_data.keys())
        )
        self.assertEqual('update', update_data['type'])
        self.assertEqual(update.existing.data, update_data['existing'])
        self.assertEqual(update.new.data, update_data['new'])
