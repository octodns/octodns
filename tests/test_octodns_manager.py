#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from os import environ
from os.path import dirname, join
from unittest import TestCase

from octodns.record import Record
from octodns.manager import _AggregateTarget, MainThreadExecutor, Manager
from octodns.yaml import safe_load
from octodns.zone import Zone

from helpers import GeoProvider, NoSshFpProvider, SimpleProvider, \
    TemporaryDirectory

config_dir = join(dirname(__file__), 'config')


def get_config_filename(which):
    return join(config_dir, which)


class TestManager(TestCase):

    def test_missing_provider_class(self):
        with self.assertRaises(Exception) as ctx:
            Manager(get_config_filename('missing-provider-class.yaml')).sync()
        self.assertTrue('missing class' in ctx.exception.message)

    def test_bad_provider_class(self):
        with self.assertRaises(Exception) as ctx:
            Manager(get_config_filename('bad-provider-class.yaml')).sync()
        self.assertTrue('Unknown provider class' in ctx.exception.message)

    def test_bad_provider_class_module(self):
        with self.assertRaises(Exception) as ctx:
            Manager(get_config_filename('bad-provider-class-module.yaml')) \
                .sync()
        self.assertTrue('Unknown provider class' in ctx.exception.message)

    def test_bad_provider_class_no_module(self):
        with self.assertRaises(Exception) as ctx:
            Manager(get_config_filename('bad-provider-class-no-module.yaml')) \
                .sync()
        self.assertTrue('Unknown provider class' in ctx.exception.message)

    def test_missing_provider_config(self):
        # Missing provider config
        with self.assertRaises(Exception) as ctx:
            Manager(get_config_filename('missing-provider-config.yaml')).sync()
        self.assertTrue('provider config' in ctx.exception.message)

    def test_missing_env_config(self):
        with self.assertRaises(Exception) as ctx:
            Manager(get_config_filename('missing-provider-env.yaml')).sync()
        self.assertTrue('missing env var' in ctx.exception.message)

    def test_missing_source(self):
        with self.assertRaises(Exception) as ctx:
            Manager(get_config_filename('unknown-provider.yaml')) \
                .sync(['missing.sources.'])
        self.assertTrue('missing sources' in ctx.exception.message)

    def test_missing_targets(self):
        with self.assertRaises(Exception) as ctx:
            Manager(get_config_filename('unknown-provider.yaml')) \
                .sync(['missing.targets.'])
        self.assertTrue('missing targets' in ctx.exception.message)

    def test_unknown_source(self):
        with self.assertRaises(Exception) as ctx:
            Manager(get_config_filename('unknown-provider.yaml')) \
                .sync(['unknown.source.'])
        self.assertTrue('unknown source' in ctx.exception.message)

    def test_unknown_target(self):
        with self.assertRaises(Exception) as ctx:
            Manager(get_config_filename('unknown-provider.yaml')) \
                .sync(['unknown.target.'])
        self.assertTrue('unknown target' in ctx.exception.message)

    def test_bad_plan_output_class(self):
        with self.assertRaises(Exception) as ctx:
            name = 'bad-plan-output-missing-class.yaml'
            Manager(get_config_filename(name)).sync()
        self.assertEquals('plan_output bad is missing class',
                          ctx.exception.message)

    def test_bad_plan_output_config(self):
        with self.assertRaises(Exception) as ctx:
            Manager(get_config_filename('bad-plan-output-config.yaml')).sync()
        self.assertEqual('Incorrect plan_output config for bad',
                         ctx.exception.message)

    def test_source_only_as_a_target(self):
        with self.assertRaises(Exception) as ctx:
            Manager(get_config_filename('unknown-provider.yaml')) \
                .sync(['not.targetable.'])
        self.assertTrue('does not support targeting' in ctx.exception.message)

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
            self.assertEquals(21, tc)

            # try with just one of the zones
            tc = Manager(get_config_filename('simple.yaml')) \
                .sync(dry_run=False, eligible_zones=['unit.tests.'])
            self.assertEquals(15, tc)

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
            self.assertEquals(21, tc)

            # Again with max_workers = 1
            tc = Manager(get_config_filename('simple.yaml'), max_workers=1) \
                .sync(dry_run=False, force=True)
            self.assertEquals(21, tc)

            # Include meta
            tc = Manager(get_config_filename('simple.yaml'), max_workers=1,
                         include_meta=True) \
                .sync(dry_run=False, force=True)
            self.assertEquals(25, tc)

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
            self.assertEquals(15, len(changes))

            # Compound sources with varying support
            changes = manager.compare(['in', 'nosshfp'],
                                      ['dump'],
                                      'unit.tests.')
            self.assertEquals(14, len(changes))

            with self.assertRaises(Exception) as ctx:
                manager.compare(['nope'], ['dump'], 'unit.tests.')
            self.assertEquals('Unknown source: nope', ctx.exception.message)

    def test_aggregate_target(self):
        simple = SimpleProvider()
        geo = GeoProvider()
        nosshfp = NoSshFpProvider()

        self.assertFalse(_AggregateTarget([simple, simple]).SUPPORTS_GEO)
        self.assertFalse(_AggregateTarget([simple, geo]).SUPPORTS_GEO)
        self.assertFalse(_AggregateTarget([geo, simple]).SUPPORTS_GEO)
        self.assertTrue(_AggregateTarget([geo, geo]).SUPPORTS_GEO)

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

            with self.assertRaises(Exception) as ctx:
                manager.dump('unit.tests.', tmpdir.dirname, False, 'nope')
            self.assertEquals('Unknown source: nope', ctx.exception.message)

            manager.dump('unit.tests.', tmpdir.dirname, False, 'in')

            # make sure this fails with an IOError and not a KeyError when
            # tyring to find sub zones
            with self.assertRaises(IOError):
                manager.dump('unknown.zone.', tmpdir.dirname, False, 'in')

    def test_dump_empty(self):
        with TemporaryDirectory() as tmpdir:
            environ['YAML_TMP_DIR'] = tmpdir.dirname
            manager = Manager(get_config_filename('simple.yaml'))

            manager.dump('empty.', tmpdir.dirname, False, 'in')

            with open(join(tmpdir.dirname, 'empty.yaml')) as fh:
                data = safe_load(fh, False)
                self.assertFalse(data)

    def test_validate_configs(self):
        Manager(get_config_filename('simple-validate.yaml')).validate_configs()

        with self.assertRaises(Exception) as ctx:
            Manager(get_config_filename('missing-sources.yaml')) \
                .validate_configs()
        self.assertTrue('missing sources' in ctx.exception.message)

        with self.assertRaises(Exception) as ctx:
            Manager(get_config_filename('unknown-provider.yaml')) \
                .validate_configs()
        self.assertTrue('unknown source' in ctx.exception.message)


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
