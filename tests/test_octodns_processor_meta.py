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


class DummyTarget:
    id = 'dummy'


dummy_target = DummyTarget()


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

    not_txt = Record.new(
        zone,
        'cname',
        {'type': 'CNAME', 'ttl': 61, 'value': 'points.to.something.'},
    )

    @patch('octodns.processor.meta.MetaProcessor.get_time')
    @patch('octodns.processor.meta.MetaProcessor.get_uuid')
    def test_args_and_values(self, get_uuid_mock, get_time_mock):
        # defaults, just time
        get_uuid_mock.side_effect = [Exception('not used')]
        get_time_mock.side_effect = ['the-time']
        proc = MetaProcessor('test')
        self.assertEqual(['time=the-time'], proc.values('dummy'))

        # just uuid
        get_uuid_mock.side_effect = ['abcdef-1234567890']
        get_time_mock.side_effect = [Exception('not used')]
        proc = MetaProcessor('test', include_time=False, include_uuid=True)
        self.assertEqual(['uuid=abcdef-1234567890'], proc.values('dummy'))

        # just version
        get_uuid_mock.side_effect = [Exception('not used')]
        get_time_mock.side_effect = [Exception('not used')]
        proc = MetaProcessor('test', include_time=False, include_version=True)
        self.assertEqual(
            [f'octodns-version={__version__}'], proc.values('dummy')
        )

        # just provider
        proc = MetaProcessor('test', include_time=False, include_provider=True)
        self.assertTrue(proc.include_provider)
        self.assertEqual(['provider=dummy'], proc.values('dummy'))

        # everything
        get_uuid_mock.side_effect = ['abcdef-1234567890']
        get_time_mock.side_effect = ['the-time']
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
                'provider=dummy-x',
                'time=the-time',
                'uuid=abcdef-1234567890',
            ],
            list(proc.values('dummy-x')),
        )
        self.assertTrue(proc.include_provider)

    def test_uuid(self):
        proc = MetaProcessor('test', include_time=False, include_uuid=True)
        self.assertTrue(proc.uuid)
        self.assertFalse(proc.time)
        self.assertFalse(proc.include_provider)
        self.assertFalse(proc.include_version)

        values = list(proc.values('dummy'))
        self.assertEqual(1, len(values))
        value = values[0]
        self.assertEqual(f'uuid={proc.uuid}', value)

    def test_is_up_to_date_meta(self):
        proc = MetaProcessor('test')

        # Creates always need to happen
        self.assertFalse(
            proc._is_up_to_date_meta(Create(self.meta_needs_update), 'dummy')
        )
        self.assertFalse(
            proc._is_up_to_date_meta(Create(self.meta_up_to_date), 'dummy')
        )

        # Updates depend on the contents
        self.assertFalse(
            proc._is_up_to_date_meta(
                Update(self.meta_needs_update, None), 'dummy'
            )
        )
        self.assertTrue(
            proc._is_up_to_date_meta(
                Update(self.meta_up_to_date, None), 'dummy'
            )
        )

        # not a meta txt
        self.assertFalse(
            proc._is_up_to_date_meta(Update(self.not_meta, None), 'dummy')
        )

        # not even a txt record
        self.assertFalse(
            proc._is_up_to_date_meta(Update(self.not_txt, None), 'dummy')
        )

    @patch('octodns.processor.meta.MetaProcessor.get_time')
    def test_process_source_and_target_zones(self, get_time_mock):
        get_time_mock.side_effect = [
            'the-time',
            'the-time-2',
            'the-time-3',
            'the-time-4',
        ]

        proc = MetaProcessor('test')
        self.assertFalse(proc.uuid)
        self.assertTrue(proc.time)
        self.assertFalse(proc.include_provider)
        self.assertFalse(proc.include_version)

        existing = self.zone.copy()
        desired = self.zone.copy()
        processed, _ = proc.process_source_and_target_zones(
            desired, existing, dummy_target
        )
        record = next(iter(processed.records))
        self.assertEqual(self.meta_up_to_date, record)
        self.assertEqual(['time=the-time'], record.values)

        # with defaults, not enabled
        existing = self.zone.copy()
        desired = self.zone.copy()
        processed, _ = proc.process_source_and_target_zones(
            desired, existing, dummy_target
        )
        records = processed.records
        self.assertEqual(1, len(records))
        record = next(iter(records))
        self.assertEqual(proc.record_name, record.name)
        self.assertEqual('TXT', record._type)
        self.assertEqual(['time=the-time'], record.values)

        # enable provider
        proc = MetaProcessor('test', include_provider=True)
        self.assertFalse(proc.uuid)
        self.assertTrue(proc.time)
        self.assertTrue(proc.include_provider)
        self.assertFalse(proc.include_version)

        existing = self.zone.copy()
        desired = self.zone.copy()
        processed, _ = proc.process_source_and_target_zones(
            existing, desired, dummy_target
        )
        record = next(iter(processed.records))
        self.assertEqual(['provider=dummy', 'time=the-time-2'], record.values)

    def test_process_plan(self):
        proc = MetaProcessor('test')

        # no plan, shouldn't happen, but we shouldn't blow up
        self.assertFalse(proc.process_plan(None, None, None))

        # plan with only a meta record that has the correct config/keys
        plan = Plan(
            None,  # ignored
            None,  # ignored
            [Update(self.meta_up_to_date, self.meta_up_to_date)],
            True,
        )
        self.assertFalse(proc.process_plan(plan, [], dummy_target))

        # plan with only a meta record that has the wrong config/keys and thus
        # needs updating
        plan = Plan(
            None,
            None,
            [Update(self.meta_needs_update, self.meta_up_to_date)],
            True,
        )
        self.assertEqual(plan, proc.process_plan(plan, [], dummy_target))

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
        self.assertEqual(plan, proc.process_plan(plan, [], dummy_target))

    def test_flow(self):
        proc = MetaProcessor(
            'test',
            record_name='special',
            include_version=True,
            include_provider=True,
            include_time=False,
        )

        desired = self.zone.copy()
        # start out with no records
        self.assertFalse(desired.records)

        # now process source and target zones (existing isn't touched)
        desired, _ = proc.process_source_and_target_zones(
            desired, [], dummy_target
        )
        records = desired.records
        self.assertEqual(1, len(records))
        meta = next(iter(records))
        # has the expected type and name & type
        self.assertEqual(proc.record_name, meta.name)
        self.assertEqual('TXT', meta._type)
        # at this point values will just have version, no provider yet b/c it
        # wasn't known
        self.assertEqual(
            [f'octodns-version={__version__}', 'provider=dummy'], meta.values
        )

        # process the plan (Create)
        plan = Plan(desired, self.zone, [Create(meta)], True)
        got = proc.process_plan(plan, [], dummy_target)
        self.assertTrue(got)

        # process the plan (Update w/no changes)
        plan = Plan(desired, self.zone, [Update(meta, meta)], True)
        got = proc.process_plan(plan, [], dummy_target)
        self.assertFalse(got)
