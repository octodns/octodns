#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from os import environ
from os.path import dirname, join
from six import text_type
from unittest import TestCase

from octodns.record import Record
from octodns.manager import _AggregateTarget, MainThreadExecutor, Manager, \
    ManagerException
from octodns.yaml import safe_load
from octodns.zone import Zone

from helpers import DynamicProvider, GeoProvider, NoSshFpProvider, \
    SimpleProvider, TemporaryDirectory, RootNsProvider

config_dir = join(dirname(__file__), 'config')


def get_config_filename(which):
    return join(config_dir, which)


class TestManager(TestCase):

    def test_missing_provider_class(self):
        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('missing-provider-class.yaml')).sync()
        self.assertTrue('missing class' in text_type(ctx.exception))

    def test_bad_provider_class(self):
        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('bad-provider-class.yaml')).sync()
        self.assertTrue('Unknown provider class' in text_type(ctx.exception))

    def test_bad_provider_class_module(self):
        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('bad-provider-class-module.yaml')) \
                .sync()
        self.assertTrue('Unknown provider class' in text_type(ctx.exception))

    def test_bad_provider_class_no_module(self):
        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('bad-provider-class-no-module.yaml')) \
                .sync()
        self.assertTrue('Unknown provider class' in text_type(ctx.exception))

    def test_missing_provider_config(self):
        # Missing provider config
        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('missing-provider-config.yaml')).sync()
        self.assertTrue('provider config' in text_type(ctx.exception))

    def test_missing_env_config(self):
        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('missing-provider-env.yaml')).sync()
        self.assertTrue('missing env var' in text_type(ctx.exception))

    def test_missing_source(self):
        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('provider-problems.yaml')) \
                .sync(['missing.sources.'])
        self.assertTrue('missing sources' in text_type(ctx.exception))

    def test_missing_targets(self):
        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('provider-problems.yaml')) \
                .sync(['missing.targets.'])
        self.assertTrue('missing targets' in text_type(ctx.exception))

    def test_unknown_source(self):
        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('provider-problems.yaml')) \
                .sync(['unknown.source.'])
        self.assertTrue('unknown source' in text_type(ctx.exception))

    def test_unknown_target(self):
        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('provider-problems.yaml')) \
                .sync(['unknown.target.'])
        self.assertTrue('unknown target' in text_type(ctx.exception))

    def test_bad_plan_output_class(self):
        with self.assertRaises(ManagerException) as ctx:
            name = 'bad-plan-output-missing-class.yaml'
            Manager(get_config_filename(name)).sync()
        self.assertEquals('plan_output bad is missing class',
                          text_type(ctx.exception))

    def test_bad_plan_output_config(self):
        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('bad-plan-output-config.yaml')).sync()
        self.assertEqual('Incorrect plan_output config for bad',
                         text_type(ctx.exception))

    def test_source_only_as_a_target(self):
        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('provider-problems.yaml')) \
                .sync(['not.targetable.'])
        self.assertTrue('does not support targeting' in
                        text_type(ctx.exception))

    def test_always_dry_run(self):
        with TemporaryDirectory() as tmpdir:
            environ['YAML_TMP_DIR'] = tmpdir.dirname
            tc = Manager(get_config_filename('always-dry-run.yaml')) \
                .sync(dry_run=False)
            # only the stuff from subzone, unit.tests. is always-dry-run
            self.assertEquals(3, tc)

    def test_simple(self):
        with TemporaryDirectory() as tmpdir:
            environ['YAML_TMP_DIR'] = tmpdir.dirname
            tc = Manager(get_config_filename('simple.yaml')) \
                .sync(dry_run=False)
            self.assertEquals(22, tc)

            # try with just one of the zones
            tc = Manager(get_config_filename('simple.yaml')) \
                .sync(dry_run=False, eligible_zones=['unit.tests.'])
            self.assertEquals(16, tc)

            # the subzone, with 2 targets
            tc = Manager(get_config_filename('simple.yaml')) \
                .sync(dry_run=False, eligible_zones=['subzone.unit.tests.'])
            self.assertEquals(6, tc)

            # and finally the empty zone
            tc = Manager(get_config_filename('simple.yaml')) \
                .sync(dry_run=False, eligible_zones=['empty.'])
            self.assertEquals(0, tc)

            # Again with force
            tc = Manager(get_config_filename('simple.yaml')) \
                .sync(dry_run=False, force=True)
            self.assertEquals(22, tc)

            # Again with max_workers = 1
            tc = Manager(get_config_filename('simple.yaml'), max_workers=1) \
                .sync(dry_run=False, force=True)
            self.assertEquals(22, tc)

            # Include meta
            tc = Manager(get_config_filename('simple.yaml'), max_workers=1,
                         include_meta=True) \
                .sync(dry_run=False, force=True)
            self.assertEquals(26, tc)

    def test_eligible_targets(self):
        with TemporaryDirectory() as tmpdir:
            environ['YAML_TMP_DIR'] = tmpdir.dirname
            # Only allow a target that doesn't exist
            tc = Manager(get_config_filename('simple.yaml')) \
                .sync(eligible_targets=['foo'])
            self.assertEquals(0, tc)

    def test_compare(self):
        with TemporaryDirectory() as tmpdir:
            environ['YAML_TMP_DIR'] = tmpdir.dirname
            manager = Manager(get_config_filename('simple.yaml'))

            # make sure this was pulled in from the config
            self.assertEquals(2, manager._executor._max_workers)

            changes = manager.compare(['in'], ['in'], 'unit.tests.')
            self.assertEquals([], changes)

            # Create an empty unit.test zone config
            with open(join(tmpdir.dirname, 'unit.tests.yaml'), 'w') as fh:
                fh.write('---\n{}')

            changes = manager.compare(['in'], ['dump'], 'unit.tests.')
            self.assertEquals(16, len(changes))

            # Compound sources with varying support
            changes = manager.compare(['in', 'nosshfp'],
                                      ['dump'],
                                      'unit.tests.')
            self.assertEquals(15, len(changes))

            with self.assertRaises(ManagerException) as ctx:
                manager.compare(['nope'], ['dump'], 'unit.tests.')
            self.assertEquals('Unknown source: nope', text_type(ctx.exception))

    def test_aggregate_target(self):
        simple = SimpleProvider()
        geo = GeoProvider()
        dynamic = DynamicProvider()
        rootns = RootNsProvider()
        nosshfp = NoSshFpProvider()

        self.assertFalse(_AggregateTarget([simple, simple]).SUPPORTS_GEO)
        self.assertFalse(_AggregateTarget([simple, geo]).SUPPORTS_GEO)
        self.assertFalse(_AggregateTarget([geo, simple]).SUPPORTS_GEO)
        self.assertTrue(_AggregateTarget([geo, geo]).SUPPORTS_GEO)

        self.assertFalse(_AggregateTarget([simple, simple]).SUPPORTS_DYNAMIC)
        self.assertFalse(_AggregateTarget([simple, dynamic]).SUPPORTS_DYNAMIC)
        self.assertFalse(_AggregateTarget([dynamic, simple]).SUPPORTS_DYNAMIC)
        self.assertTrue(_AggregateTarget([dynamic, dynamic]).SUPPORTS_DYNAMIC)

        self.assertFalse(_AggregateTarget([simple, simple]).SUPPORTS_ROOT_NS)
        self.assertFalse(_AggregateTarget([simple, rootns]).SUPPORTS_ROOT_NS)
        self.assertFalse(_AggregateTarget([rootns, simple]).SUPPORTS_ROOT_NS)
        self.assertTrue(_AggregateTarget([rootns, rootns]).SUPPORTS_ROOT_NS)

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
            self.assertEquals('Unknown source: nope', text_type(ctx.exception))

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
            self.assertEquals('Unknown source: nope', text_type(ctx.exception))

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
        self.assertTrue('missing sources' in text_type(ctx.exception))

        with self.assertRaises(ManagerException) as ctx:
            Manager(get_config_filename('unknown-provider.yaml')) \
                .validate_configs()
        self.assertTrue('unknown source' in text_type(ctx.exception))


class TestMainThreadExecutor(TestCase):

    def test_success(self):
        mte = MainThreadExecutor()

        future = mte.submit(self.success, 42)
        self.assertEquals(42, future.result())

        future = mte.submit(self.success, ret=43)
        self.assertEquals(43, future.result())

    def test_exception(self):
        mte = MainThreadExecutor()

        e = Exception('boom')
        future = mte.submit(self.exception, e)
        with self.assertRaises(Exception) as ctx:
            future.result()
        self.assertEquals(e, ctx.exception)

        future = mte.submit(self.exception, e=e)
        with self.assertRaises(Exception) as ctx:
            future.result()
        self.assertEquals(e, ctx.exception)

    def success(self, ret):
        return ret

    def exception(self, e):
        raise e
