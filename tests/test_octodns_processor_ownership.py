#
#
#

from unittest import TestCase

from helpers import PlannableProvider

from octodns.processor.ownership import OwnershipException, OwnershipProcessor
from octodns.provider.plan import Plan
from octodns.record import Delete, Record, Update, ValueMixin
from octodns.zone import DuplicateRecordException, Zone

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


class MixedCaseValue(str):
    @classmethod
    def parse_rdata_text(cls, value):
        return value

    @classmethod
    def validate(cls, data, _type):
        return []

    @classmethod
    def process(cls, value):
        return MixedCaseValue(value)

    @property
    def rdata_text(self):
        return self


class MixedCase(ValueMixin, Record):
    # Provider-specific types are not required to be upper case, e.g.
    # octodns-route53's Route53Provider/ALIAS
    _type = 'Provider/MiXeD'
    _value_type = MixedCaseValue


Record.register_type(MixedCase, 'Provider/MiXeD')


class TestOwnershipProcessor(TestCase):
    def test_process_source_zone(self):
        ownership = OwnershipProcessor('ownership')

        got = ownership.process_source_zone(zone.copy(), None)
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
                # default ttl value
                self.assertEqual(60, record.ttl)
                found = True
            else:
                self.assertFalse(ownership._is_ownership(record))
        self.assertTrue(found)

        # change the ttl from the default
        ownership.txt_ttl = 300
        got = ownership.process_source_zone(zone.copy(), None)
        record = next(
            r for r in got.records if r.name.startswith(ownership.txt_name)
        )
        self.assertEqual(300, record.ttl)

    def test_process_plan(self):
        ownership = OwnershipProcessor('ownership')
        provider = PlannableProvider('helper')

        # No plan, is a quick noop
        self.assertFalse(ownership.process_plan(None, None, None))

        # Nothing exists create both records and ownership
        ownership_added = ownership.process_source_zone(zone.copy(), None)
        plan = provider.plan(ownership_added)
        self.assertTrue(plan)
        # Double the number of records
        self.assertEqual(len(records) * 2, len(plan.changes))
        # Now process the plan, shouldn't make any changes, we're creating
        # everything
        got = ownership.process_plan(plan, None, None)
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
        got = ownership.process_plan(plan, None, None)
        self.assertTrue(got)
        self.assertEqual(len(records) * 2, len(got.changes))

        # Something extra exists and does have an ownership record so we will
        # delete it...
        copy = Zone('unit.tests.', [])
        for record in records.values():
            if record.name != 'the-a':
                copy.add_record(record)
        # New ownership, without the `the-a`
        ownership_added = ownership.process_source_zone(copy, None)
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
        got = ownership.process_plan(plan, None, None)
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
        plan = ownership.process_plan(plan, None, None)
        self.assertFalse(plan)

    def test_should_replace(self):
        ownership = OwnershipProcessor('ownership')
        self.assertFalse(ownership.should_replace)

        zone = Zone('unit.tests.', [])
        record = Record.new(
            zone, 'a', {'ttl': 30, 'type': 'A', 'value': '4.4.4.4'}
        )
        zone.add_record(record)

        got = ownership.process_source_zone(zone.copy(), None)
        self.assertEqual(
            ['_owner.a.a', 'a'], sorted([r.name for r in got.records])
        )

        # will fail w/a duplicate
        with self.assertRaises(DuplicateRecordException):
            ownership.process_source_zone(got.copy(), None)

        # enable should_replace, will replace instead of failing
        ownership.should_replace = True
        got = ownership.process_source_zone(got.copy(), None)
        # same expected result
        self.assertEqual(
            ['_owner.a.a', 'a'], sorted([r.name for r in got.records])
        )

    def test_allow_takeover(self):
        ownership = OwnershipProcessor('ownership')
        # disallowed by default
        self.assertFalse(ownership.allow_takeover)

        provider = PlannableProvider('helper')

        # `the-a` is managed by us (and thus has its ownership marker in
        # plan.desired), but a foreign ownership record for it already
        # exists in plan.existing
        ownership_added = ownership.process_source_zone(zone.copy(), None)
        plan = provider.plan(ownership_added)

        the_a = records['the-a']
        plan.existing.add_record(the_a)
        foreign_ownership = Record.new(
            zone,
            f'{ownership.txt_name}.a.the-a',
            {'ttl': 30, 'type': 'TXT', 'value': 'someone-else'},
        )
        plan.existing.add_record(foreign_ownership)

        with self.assertRaises(OwnershipException) as ctx:
            ownership.process_plan(plan, None, None)
        self.assertIn('the-a', str(ctx.exception))
        self.assertIn('someone-else', str(ctx.exception))

        # opting in restores the old, silent takeover behavior
        ownership.allow_takeover = True
        got = ownership.process_plan(plan, None, None)
        self.assertTrue(got)

        # a foreign ownership record for something we don't manage is left
        # alone and does not raise, regardless of allow_takeover
        ownership.allow_takeover = False
        plan = provider.plan(ownership_added)
        foreign_unmanaged = Record.new(
            zone,
            f'{ownership.txt_name}.a.extra-a',
            {'ttl': 30, 'type': 'TXT', 'value': 'someone-else'},
        )
        plan.existing.add_record(foreign_unmanaged)
        got = ownership.process_plan(plan, None, None)
        self.assertTrue(got)

    def test_process_plan_mixed_case_type(self):
        # Record names are lower cased, so the ownership TXT for a
        # provider-specific type records that type in lower case. The plan
        # filter has to account for that or changes to those records are
        # silently dropped even though we own them.
        ownership = OwnershipProcessor('ownership')

        zone = Zone('unit.tests.', [])
        record = Record.new(
            zone,
            'mixed',
            {'ttl': 30, 'type': 'Provider/MiXeD', 'value': 'before'},
        )
        updated = Record.new(
            zone,
            'mixed',
            {'ttl': 30, 'type': 'Provider/MiXeD', 'value': 'after'},
        )

        marker = Record.new(
            zone,
            f'{ownership.txt_name}.provider/mixed.mixed',
            {'ttl': 60, 'type': 'TXT', 'value': ownership.txt_value},
            lenient=True,
        )
        # the marker name is lower cased on the way in
        self.assertEqual(
            f'{ownership.txt_name}.provider/mixed.mixed', marker.name
        )

        existing = Zone(zone.name, [])
        desired = Zone(zone.name, [])
        for zone_, value in ((existing, record), (desired, updated)):
            zone_.add_record(value, lenient=True)
            zone_.add_record(marker, lenient=True)

        change = Update(record, updated)
        plan = Plan(existing, desired, [change], True)

        got = ownership.process_plan(plan, None, None)
        self.assertTrue(got)
        self.assertEqual([change], got.changes)

        # an unowned record of the same type is still left alone
        unowned = Record.new(
            zone,
            'unowned',
            {'ttl': 30, 'type': 'Provider/MiXeD', 'value': 'before'},
        )
        existing = Zone(zone.name, [])
        existing.add_record(unowned, lenient=True)
        plan = Plan(existing, Zone(zone.name, []), [Delete(unowned)], True)
        self.assertFalse(ownership.process_plan(plan, None, None))
