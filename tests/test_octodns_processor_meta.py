#
#
#

from unittest import TestCase
from unittest.mock import patch

from octodns import __version__
from octodns.processor.meta import MetaProcessor
from octodns.provider.plan import Plan
from octodns.record import Create, Record, Update
from octodns.zone import Zone


class TestMetaProcessor(TestCase):
    zone = Zone('unit.tests.', [])

    meta_needs_update = Record.new(
        zone,
        'meta',
        {
            'type': 'TXT',
            'ttl': 60,
            # will always need updating
            'values': ['uuid'],
        },
    )

    meta_up_to_date = Record.new(
        zone,
        'meta',
        {
            'type': 'TXT',
            'ttl': 60,
            # only has time, value should be ignored
            'values': ['time=xxx'],
        },
    )

    not_meta = Record.new(
        zone,
        'its-not-meta',
        {
            'type': 'TXT',
            'ttl': 60,
            # has time, but name is wrong so won't matter
            'values': ['time=xyz'],
        },
    )

    @patch('octodns.processor.meta.MetaProcessor.now')
    @patch('octodns.processor.meta.MetaProcessor.uuid')
    def test_args_and_values(self, uuid_mock, now_mock):
        # defaults, just time
        uuid_mock.side_effect = [Exception('not used')]
        now_mock.side_effect = ['the-time']
        proc = MetaProcessor('test')
        self.assertEqual(['time=the-time'], proc.values)

        # just uuid
        uuid_mock.side_effect = ['abcdef-1234567890']
        now_mock.side_effect = [Exception('not used')]
        proc = MetaProcessor('test', include_time=False, include_uuid=True)
        self.assertEqual(['uuid=abcdef-1234567890'], proc.values)

        # just version
        uuid_mock.side_effect = [Exception('not used')]
        now_mock.side_effect = [Exception('not used')]
        proc = MetaProcessor('test', include_time=False, include_version=True)
        self.assertEqual([f'octodns-version={__version__}'], proc.values)

        # just provider
        proc = MetaProcessor('test', include_time=False, include_provider=True)
        self.assertTrue(proc.include_provider)
        self.assertFalse(proc.values)

        # everything
        uuid_mock.side_effect = ['abcdef-1234567890']
        now_mock.side_effect = ['the-time']
        proc = MetaProcessor(
            'test',
            include_time=True,
            include_uuid=True,
            include_version=True,
            include_provider=True,
        )
        self.assertEqual(
            [
                f'octodns-version={__version__}',
                'time=the-time',
                'uuid=abcdef-1234567890',
            ],
            proc.values,
        )
        self.assertTrue(proc.include_provider)

    def test_uuid(self):
        proc = MetaProcessor('test', include_time=False, include_uuid=True)
        self.assertEqual(1, len(proc.values))
        self.assertTrue(proc.values[0].startswith('uuid'))
        # uuid's have 4 -
        self.assertEqual(4, proc.values[0].count('-'))

    def test_up_to_date(self):
        proc = MetaProcessor('test')

        # Creates always need to happen
        self.assertFalse(proc._up_to_date(Create(self.meta_needs_update)))
        self.assertFalse(proc._up_to_date(Create(self.meta_up_to_date)))

        # Updates depend on the contents
        self.assertFalse(proc._up_to_date(Update(self.meta_needs_update, None)))
        self.assertTrue(proc._up_to_date(Update(self.meta_up_to_date, None)))

    @patch('octodns.processor.meta.MetaProcessor.now')
    def test_process_source_zone(self, now_mock):
        now_mock.side_effect = ['the-time']
        proc = MetaProcessor('test')

        # meta record was added
        desired = self.zone.copy()
        processed = proc.process_source_zone(desired, None)
        record = next(iter(processed.records))
        self.assertEqual(self.meta_up_to_date, record)
        self.assertEqual(['time=the-time'], record.values)

    def test_process_source_and_target_zones(self):
        proc = MetaProcessor('test')

        # with defaults, not enabled
        existing = self.zone.copy()
        desired = self.zone.copy()
        processed, _ = proc.process_source_and_target_zones(
            existing, desired, None
        )
        self.assertFalse(processed.records)

        # enable provider
        proc = MetaProcessor('test', include_provider=True)

        class DummyTarget:
            id = 'dummy'

        # enabled provider, no meta record, shouldn't happen, but also shouldn't
        # blow up
        processed, _ = proc.process_source_and_target_zones(
            existing, desired, DummyTarget()
        )
        self.assertFalse(processed.records)

        # enabled provider, should now look for and update the provider value,
        # - only record so nothing to skip over
        # - time value in there to be skipped over
        proc = MetaProcessor('test', include_provider=True)
        existing = self.zone.copy()
        desired = self.zone.copy()
        meta = self.meta_up_to_date.copy()
        existing.add_record(meta)
        processed, _ = proc.process_source_and_target_zones(
            existing, desired, DummyTarget()
        )
        record = next(iter(processed.records))
        self.assertEqual(['provider=dummy', 'time=xxx'], record.values)

        # add another unrelated record that needs to be skipped
        proc = MetaProcessor('test', include_provider=True)
        existing = self.zone.copy()
        desired = self.zone.copy()
        meta = self.meta_up_to_date.copy()
        existing.add_record(meta)
        existing.add_record(self.not_meta)
        processed, _ = proc.process_source_and_target_zones(
            existing, desired, DummyTarget()
        )
        self.assertEqual(2, len(processed.records))
        record = [r for r in processed.records if r.name == proc.record_name][0]
        self.assertEqual(['provider=dummy', 'time=xxx'], record.values)

    def test_process_plan(self):
        proc = MetaProcessor('test')

        # no plan, shouldn't happen, but we shouldn't blow up
        self.assertFalse(proc.process_plan(None, None, None))

        # plan with just an up to date meta record, should kill off the plan
        plan = Plan(
            None,
            None,
            [Update(self.meta_up_to_date, self.meta_needs_update)],
            True,
        )
        self.assertFalse(proc.process_plan(plan, None, None))

        # plan with an out of date meta record, should leave the plan alone
        plan = Plan(
            None,
            None,
            [Update(self.meta_needs_update, self.meta_up_to_date)],
            True,
        )
        self.assertEqual(plan, proc.process_plan(plan, None, None))

        # plan with other changes preserved even if meta was somehow up to date
        plan = Plan(
            None,
            None,
            [
                Update(self.meta_up_to_date, self.meta_needs_update),
                Create(self.not_meta),
            ],
            True,
        )
        self.assertEqual(plan, proc.process_plan(plan, None, None))
