#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from os import environ
from os.path import dirname, join

from octodns import __VERSION__
from octodns.manager import _AggregateTarget, MainThreadExecutor, Manager, \
    ManagerException
from octodns.processor.base import BaseProcessor
from octodns.record import Create, Delete, Record
from octodns.yaml import safe_load
from octodns.zone import Zone

from unittest import TestCase
from unittest.mock import MagicMock, patch

from helpers import DynamicProvider, GeoProvider, NoSshFpProvider, \
    PlannableProvider, SimpleProvider, TemporaryDirectory

config_dir = join(dirname(__file__), 'config')


def get_config_filename(which):
    return join(config_dir, which)


class TestManager(TestCase):

    def test_missing_provider_class(self):
        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('missing-provider-class.yaml')).sync()
        self.assertTrue('missing class' in str(ctx.exception))

    def test_bad_provider_class(self):
        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('bad-provider-class.yaml')).sync()
        self.assertTrue('Unknown provider class' in str(ctx.exception))

    def test_bad_provider_class_module(self):
        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('bad-provider-class-module.yaml')) \
                .sync()
        self.assertTrue('Unknown provider class' in str(ctx.exception))

    def test_bad_provider_class_no_module(self):
        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('bad-provider-class-no-module.yaml')) \
                .sync()
        self.assertTrue('Unknown provider class' in str(ctx.exception))

    def test_missing_provider_config(self):
        # Missing provider config
        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('missing-provider-config.yaml')).sync()
        self.assertTrue('provider config' in str(ctx.exception))

    def test_missing_env_config(self):
        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('missing-provider-env.yaml')).sync()
        self.assertTrue('missing env var' in str(ctx.exception))

    def test_missing_source(self):
        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('provider-problems.yaml')) \
                .sync(['missing.sources.'])
        self.assertTrue('missing sources' in str(ctx.exception))

    def test_missing_targets(self):
        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('provider-problems.yaml')) \
                .sync(['missing.targets.'])
        self.assertTrue('missing targets' in str(ctx.exception))

    def test_unknown_source(self):
        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('provider-problems.yaml')) \
                .sync(['unknown.source.'])
        self.assertTrue('unknown source' in str(ctx.exception))

    def test_unknown_target(self):
        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('provider-problems.yaml')) \
                .sync(['unknown.target.'])
        self.assertTrue('unknown target' in str(ctx.exception))

    def test_bad_plan_output_class(self):
        with self.assertRaises(ManagerException) as ctx:
            name = 'bad-plan-output-missing-class.yaml'
            Manager(get_config_filename(name)).sync()
        self.assertEqual('plan_output bad is missing class',
                         str(ctx.exception))

    def test_bad_plan_output_config(self):
        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('bad-plan-output-config.yaml')).sync()
        self.assertEqual('Incorrect plan_output config for bad',
                         str(ctx.exception))

    def test_source_only_as_a_target(self):
        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('provider-problems.yaml')) \
                .sync(['not.targetable.'])
        self.assertTrue('does not support targeting' in
                        str(ctx.exception))

    def test_always_dry_run(self):
        with TemporaryDirectory() as tmpdir:
            environ['YAML_TMP_DIR'] = tmpdir.dirname
            tc = Manager(get_config_filename('always-dry-run.yaml')) \
                .sync(dry_run=False)
            # only the stuff from subzone, unit.tests. is always-dry-run
            self.assertEqual(3, tc)

    def test_simple(self):
        with TemporaryDirectory() as tmpdir:
            environ['YAML_TMP_DIR'] = tmpdir.dirname
            tc = Manager(get_config_filename('simple.yaml')) \
                .sync(dry_run=False)
            self.assertEqual(26, tc)

            # try with just one of the zones
            tc = Manager(get_config_filename('simple.yaml')) \
                .sync(dry_run=False, eligible_zones=['unit.tests.'])
            self.assertEqual(20, tc)

            # the subzone, with 2 targets
            tc = Manager(get_config_filename('simple.yaml')) \
                .sync(dry_run=False, eligible_zones=['subzone.unit.tests.'])
            self.assertEqual(6, tc)

            # and finally the empty zone
            tc = Manager(get_config_filename('simple.yaml')) \
                .sync(dry_run=False, eligible_zones=['empty.'])
            self.assertEqual(0, tc)

            # Again with force
            tc = Manager(get_config_filename('simple.yaml')) \
                .sync(dry_run=False, force=True)
            self.assertEqual(26, tc)

            # Again with max_workers = 1
            tc = Manager(get_config_filename('simple.yaml'), max_workers=1) \
                .sync(dry_run=False, force=True)
            self.assertEqual(26, tc)

            # Include meta
            tc = Manager(get_config_filename('simple.yaml'), max_workers=1,
                         include_meta=True) \
                .sync(dry_run=False, force=True)
            self.assertEqual(30, tc)

    def test_eligible_sources(self):
        with TemporaryDirectory() as tmpdir:
            environ['YAML_TMP_DIR'] = tmpdir.dirname
            # Only allow a target that doesn't exist
            tc = Manager(get_config_filename('simple.yaml')) \
                .sync(eligible_sources=['foo'])
            self.assertEqual(0, tc)

    def test_eligible_targets(self):
        with TemporaryDirectory() as tmpdir:
            environ['YAML_TMP_DIR'] = tmpdir.dirname
            # Only allow a target that doesn't exist
            tc = Manager(get_config_filename('simple.yaml')) \
                .sync(eligible_targets=['foo'])
            self.assertEqual(0, tc)

    def test_aliases(self):
        with TemporaryDirectory() as tmpdir:
            environ['YAML_TMP_DIR'] = tmpdir.dirname
            # Alias zones with a valid target.
            tc = Manager(get_config_filename('simple-alias-zone.yaml')) \
                .sync()
            self.assertEqual(0, tc)

            # Alias zone with an invalid target.
            with self.assertRaises(ManagerException) as ctx:
                tc = Manager(get_config_filename('unknown-source-zone.yaml')) \
                    .sync()
            self.assertEqual('Invalid alias zone alias.tests.: source zone '
                             'does-not-exists.tests. does not exist',
                             str(ctx.exception))

            # Alias zone that points to another alias zone.
            with self.assertRaises(ManagerException) as ctx:
                tc = Manager(get_config_filename('alias-zone-loop.yaml')) \
                    .sync()
            self.assertEqual('Invalid alias zone alias-loop.tests.: source '
                             'zone alias.tests. is an alias zone',
                             str(ctx.exception))

            # Sync an alias without the zone it refers to
            with self.assertRaises(ManagerException) as ctx:
                tc = Manager(get_config_filename('simple-alias-zone.yaml')) \
                    .sync(eligible_zones=["alias.tests."])
            self.assertEqual('Zone alias.tests. cannot be sync without zone '
                             'unit.tests. sinced it is aliased',
                             str(ctx.exception))

    def test_compare(self):
        with TemporaryDirectory() as tmpdir:
            environ['YAML_TMP_DIR'] = tmpdir.dirname
            manager = Manager(get_config_filename('simple.yaml'))

            # make sure this was pulled in from the config
            self.assertEqual(2, manager._executor._max_workers)

            changes = manager.compare(['in'], ['in'], 'unit.tests.')
            self.assertEqual([], changes)

            # Create an empty unit.test zone config
            with open(join(tmpdir.dirname, 'unit.tests.yaml'), 'w') as fh:
                fh.write('---\n{}')

            # compare doesn't use _process_desired_zone and thus doesn't filter
            # out root NS records, that seems fine/desirable
            changes = manager.compare(['in'], ['dump'], 'unit.tests.')
            self.assertEqual(21, len(changes))

            # Compound sources with varying support
            changes = manager.compare(['in', 'nosshfp'],
                                      ['dump'],
                                      'unit.tests.')
            self.assertEqual(20, len(changes))

            with self.assertRaises(ManagerException) as ctx:
                manager.compare(['nope'], ['dump'], 'unit.tests.')
            self.assertEqual('Unknown source: nope', str(ctx.exception))

    def test_aggregate_target(self):
        simple = SimpleProvider()
        geo = GeoProvider()
        dynamic = DynamicProvider()
        nosshfp = NoSshFpProvider()

        targets = [simple, geo]
        at = _AggregateTarget(targets)
        # expected targets
        self.assertEqual(targets, at.targets)
        # union of their SUPPORTS
        self.assertEqual(set(('A')), at.SUPPORTS)

        # unknown property will go up into super and throw the normal
        # exception
        with self.assertRaises(AttributeError) as ctx:
            at.FOO
        self.assertEqual('_AggregateTarget object has no attribute FOO',
                         str(ctx.exception))

        self.assertFalse(_AggregateTarget([simple, simple]).SUPPORTS_GEO)
        self.assertFalse(_AggregateTarget([simple, geo]).SUPPORTS_GEO)
        self.assertFalse(_AggregateTarget([geo, simple]).SUPPORTS_GEO)
        self.assertTrue(_AggregateTarget([geo, geo]).SUPPORTS_GEO)

        self.assertFalse(_AggregateTarget([simple, simple]).SUPPORTS_DYNAMIC)
        self.assertFalse(_AggregateTarget([simple, dynamic]).SUPPORTS_DYNAMIC)
        self.assertFalse(_AggregateTarget([dynamic, simple]).SUPPORTS_DYNAMIC)
        self.assertTrue(_AggregateTarget([dynamic, dynamic]).SUPPORTS_DYNAMIC)

        zone = Zone('unit.tests.', [])
        record = Record.new(zone, 'sshfp', {
            'ttl': 60,
            'type': 'SSHFP',
            'value': {
                'algorithm': 1,
                'fingerprint_type': 1,
                'fingerprint': 'abcdefg',
            },
        })
        self.assertTrue(simple.supports(record))
        self.assertFalse(nosshfp.supports(record))
        self.assertTrue(_AggregateTarget([simple, simple]).supports(record))
        self.assertFalse(_AggregateTarget([simple, nosshfp]).supports(record))

    def test_dump(self):
        with TemporaryDirectory() as tmpdir:
            environ['YAML_TMP_DIR'] = tmpdir.dirname
            manager = Manager(get_config_filename('simple.yaml'))

            with self.assertRaises(ManagerException) as ctx:
                manager.dump('unit.tests.', tmpdir.dirname, False, False,
                             'nope')
            self.assertEqual('Unknown source: nope', str(ctx.exception))

            manager.dump('unit.tests.', tmpdir.dirname, False, False, 'in')

            # make sure this fails with an IOError and not a KeyError when
            # tyring to find sub zones
            with self.assertRaises(IOError):
                manager.dump('unknown.zone.', tmpdir.dirname, False, False,
                             'in')

    def test_dump_empty(self):
        with TemporaryDirectory() as tmpdir:
            environ['YAML_TMP_DIR'] = tmpdir.dirname
            manager = Manager(get_config_filename('simple.yaml'))

            manager.dump('empty.', tmpdir.dirname, False, False, 'in')

            with open(join(tmpdir.dirname, 'empty.yaml')) as fh:
                data = safe_load(fh, False)
                self.assertFalse(data)

    def test_dump_split(self):
        with TemporaryDirectory() as tmpdir:
            environ['YAML_TMP_DIR'] = tmpdir.dirname
            manager = Manager(get_config_filename('simple-split.yaml'))

            with self.assertRaises(ManagerException) as ctx:
                manager.dump('unit.tests.', tmpdir.dirname, False, True,
                             'nope')
            self.assertEqual('Unknown source: nope', str(ctx.exception))

            manager.dump('unit.tests.', tmpdir.dirname, False, True, 'in')

            # make sure this fails with an OSError and not a KeyError when
            # tyring to find sub zones
            with self.assertRaises(OSError):
                manager.dump('unknown.zone.', tmpdir.dirname, False, True,
                             'in')

    def test_validate_configs(self):
        Manager(get_config_filename('simple-validate.yaml')).validate_configs()

        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('missing-sources.yaml')) \
                .validate_configs()
        self.assertTrue('missing sources' in str(ctx.exception))

        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('unknown-provider.yaml')) \
                .validate_configs()
        self.assertTrue('unknown source' in str(ctx.exception))

        # Alias zone using an invalid source zone.
        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('unknown-source-zone.yaml')) \
                .validate_configs()
        self.assertTrue('does not exist' in str(ctx.exception))

        # Alias zone that points to another alias zone.
        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('alias-zone-loop.yaml')) \
                .validate_configs()
        self.assertTrue('is an alias zone' in str(ctx.exception))

        # Valid config file using an alias zone.
        Manager(get_config_filename('simple-alias-zone.yaml')) \
            .validate_configs()

        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('unknown-processor.yaml')) \
                .validate_configs()
        self.assertTrue('unknown processor' in str(ctx.exception))

    def test_get_zone(self):
        Manager(get_config_filename('simple.yaml')).get_zone('unit.tests.')

        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('simple.yaml')).get_zone('unit.tests')
        self.assertTrue('missing ending dot' in str(ctx.exception))

        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('simple.yaml')) \
                .get_zone('unknown-zone.tests.')
        self.assertTrue('Unknown zone name' in str(ctx.exception))

    def test_populate_lenient_fallback(self):
        with TemporaryDirectory() as tmpdir:
            environ['YAML_TMP_DIR'] = tmpdir.dirname
            # Only allow a target that doesn't exist
            manager = Manager(get_config_filename('simple.yaml'))

            class NoLenient(SimpleProvider):

                def populate(self, zone):
                    pass

            # This should be ok, we'll fall back to not passing it
            manager._populate_and_plan('unit.tests.', [], [NoLenient()], [])

            class OtherType(SimpleProvider):

                def populate(self, zone, lenient=False):
                    raise TypeError('something else')

            # This will blow up, we don't fallback for source
            with self.assertRaises(TypeError) as ctx:
                manager._populate_and_plan('unit.tests.', [], [OtherType()],
                                           [])
            self.assertEqual('something else', str(ctx.exception))

    def test_plan_processors_fallback(self):
        with TemporaryDirectory() as tmpdir:
            environ['YAML_TMP_DIR'] = tmpdir.dirname
            # Only allow a target that doesn't exist
            manager = Manager(get_config_filename('simple.yaml'))

            class NoProcessors(SimpleProvider):

                def plan(self, zone):
                    pass

            # This should be ok, we'll fall back to not passing it
            manager._populate_and_plan('unit.tests.', [], [],
                                       [NoProcessors()])

            class OtherType(SimpleProvider):

                def plan(self, zone, processors):
                    raise TypeError('something else')

            # This will blow up, we don't fallback for source
            with self.assertRaises(TypeError) as ctx:
                manager._populate_and_plan('unit.tests.', [], [],
                                           [OtherType()])
            self.assertEqual('something else', str(ctx.exception))

    @patch('octodns.manager.Manager._get_named_class')
    def test_sync_passes_file_handle(self, mock):
        plan_output_mock = MagicMock()
        plan_output_class_mock = MagicMock()
        plan_output_class_mock.return_value = plan_output_mock
        mock.return_value = (plan_output_class_mock, 'ignored', 'ignored')
        fh_mock = MagicMock()

        Manager(get_config_filename('plan-output-filehandle.yaml')
                ).sync(plan_output_fh=fh_mock)

        # Since we only care about the fh kwarg, and different _PlanOutputs are
        # are free to require arbitrary kwargs anyway, we concern ourselves
        # with checking the value of fh only.
        plan_output_mock.run.assert_called()
        _, kwargs = plan_output_mock.run.call_args
        self.assertEqual(fh_mock, kwargs.get('fh'))

    def test_processor_config(self):
        # Smoke test loading a valid config
        manager = Manager(get_config_filename('processors.yaml'))
        self.assertEqual(['noop', 'test'], list(manager.processors.keys()))
        # This zone specifies a valid processor
        manager.sync(['unit.tests.'])

        with self.assertRaises(ManagerException) as ctx:
            # This zone specifies a non-existant processor
            manager.sync(['bad.unit.tests.'])
        self.assertTrue('Zone bad.unit.tests., unknown processor: '
                        'doesnt-exist' in str(ctx.exception))

        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('processors-missing-class.yaml'))
        self.assertTrue('Processor no-class is missing class' in
                        str(ctx.exception))

        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('processors-wants-config.yaml'))
        self.assertTrue('Incorrect processor config for wants-config' in
                        str(ctx.exception))

    def test_processors(self):
        manager = Manager(get_config_filename('simple.yaml'))

        targets = [PlannableProvider('prov')]

        zone = Zone('unit.tests.', [])
        record = Record.new(zone, 'a', {
            'ttl': 30,
            'type': 'A',
            'value': '1.2.3.4',
        })

        # muck with sources
        class MockProcessor(BaseProcessor):

            def process_source_zone(self, zone, sources):
                zone = zone.copy()
                zone.add_record(record)
                return zone

        mock = MockProcessor('mock')
        plans, zone = manager._populate_and_plan('unit.tests.', [mock], [],
                                                 targets)
        # Our mock was called and added the record
        self.assertEqual(record, list(zone.records)[0])
        # We got a create for the thing added to the expected state (source)
        self.assertIsInstance(plans[0][1].changes[0], Create)

        # muck with targets
        class MockProcessor(BaseProcessor):

            def process_target_zone(self, zone, target):
                zone = zone.copy()
                zone.add_record(record)
                return zone

        mock = MockProcessor('mock')
        plans, zone = manager._populate_and_plan('unit.tests.', [mock], [],
                                                 targets)
        # No record added since it's target this time
        self.assertFalse(zone.records)
        # We got a delete for the thing added to the existing state (target)
        self.assertIsInstance(plans[0][1].changes[0], Delete)

        # muck with plans
        class MockProcessor(BaseProcessor):

            def process_target_zone(self, zone, target):
                zone = zone.copy()
                zone.add_record(record)
                return zone

            def process_plan(self, plans, sources, target):
                # get rid of the change
                plans.changes.pop(0)

        mock = MockProcessor('mock')
        plans, zone = manager._populate_and_plan('unit.tests.', [mock], [],
                                                 targets)
        # We planned a delete again, but this time removed it from the plan, so
        # no plans
        self.assertFalse(plans)

    def test_try_version(self):
        manager = Manager(get_config_filename('simple.yaml'))

        class DummyModule(object):
            __VERSION__ = '2.3.4'

        dummy_module = DummyModule()

        # use importlib.metadata.version
        self.assertTrue(__VERSION__,
                        manager._try_version('octodns',
                                             module=dummy_module,
                                             version='1.2.3'))

        # use module
        self.assertTrue(manager._try_version('doesnt-exist',
                                             module=dummy_module))

        # fall back to version, preferred over module
        self.assertEqual('1.2.3', manager._try_version('doesnt-exist',
                                                       module=dummy_module,
                                                       version='1.2.3', ))


class TestMainThreadExecutor(TestCase):

    def test_success(self):
        mte = MainThreadExecutor()

        future = mte.submit(self.success, 42)
        self.assertEqual(42, future.result())

        future = mte.submit(self.success, ret=43)
        self.assertEqual(43, future.result())

    def test_exception(self):
        mte = MainThreadExecutor()

        e = Exception('boom')
        future = mte.submit(self.exception, e)
        with self.assertRaises(Exception) as ctx:
            future.result()
        self.assertEqual(e, ctx.exception)

        future = mte.submit(self.exception, e=e)
        with self.assertRaises(Exception) as ctx:
            future.result()
        self.assertEqual(e, ctx.exception)

    def success(self, ret):
        return ret

    def exception(self, e):
        raise e
