#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from os.path import dirname, isfile, join
from unittest import TestCase
from yaml import safe_load
from yaml.constructor import ConstructorError

from octodns.record import Create
from octodns.provider.yaml import YamlProvider
from octodns.zone import SubzoneRecordException, Zone

from helpers import TemporaryDirectory


class TestYamlProvider(TestCase):

    def test_provider(self):
        source = YamlProvider('test', join(dirname(__file__), 'config'))

        zone = Zone('unit.tests.', [])
        dynamic_zone = Zone('dynamic.tests.', [])

        # With target we don't add anything
        source.populate(zone, target=source)
        self.assertEquals(0, len(zone.records))

        # without it we see everything
        source.populate(zone)
        self.assertEquals(18, len(zone.records))

        source.populate(dynamic_zone)
        self.assertEquals(4, len(dynamic_zone.records))

        # Assumption here is that a clean round-trip means that everything
        # worked as expected, data that went in came back out and could be
        # pulled in yet again and still match up. That assumes that the input
        # data completely exercises things. This assumption can be tested by
        # relatively well by running
        #   ./script/coverage tests/test_octodns_provider_yaml.py and
        # looking at the coverage file
        #   ./htmlcov/octodns_provider_yaml_py.html

        with TemporaryDirectory() as td:
            # Add some subdirs to make sure that it can create them
            directory = join(td.dirname, 'sub', 'dir')
            yaml_file = join(directory, 'unit.tests.yaml')
            dynamic_yaml_file = join(directory, 'dynamic.tests.yaml')
            target = YamlProvider('test', directory)

            # We add everything
            plan = target.plan(zone)
            self.assertEquals(15, len(filter(lambda c: isinstance(c, Create),
                                             plan.changes)))
            self.assertFalse(isfile(yaml_file))

            # Now actually do it
            self.assertEquals(15, target.apply(plan))
            self.assertTrue(isfile(yaml_file))

            # Dynamic plan
            plan = target.plan(dynamic_zone)
            self.assertEquals(4, len(filter(lambda c: isinstance(c, Create),
                                            plan.changes)))
            self.assertFalse(isfile(dynamic_yaml_file))
            # Apply it
            self.assertEquals(4, target.apply(plan))
            self.assertTrue(isfile(dynamic_yaml_file))

            # There should be no changes after the round trip
            reloaded = Zone('unit.tests.', [])
            target.populate(reloaded)
            self.assertDictEqual(
                {'included': ['test']},
                filter(
                    lambda x: x.name == 'included', reloaded.records
                )[0]._octodns)

            self.assertFalse(zone.changes(reloaded, target=source))

            # A 2nd sync should still create everything
            plan = target.plan(zone)
            self.assertEquals(15, len(filter(lambda c: isinstance(c, Create),
                                             plan.changes)))

            with open(yaml_file) as fh:
                data = safe_load(fh.read())

                # '' has some of both
                roots = sorted(data.pop(''), key=lambda r: r['type'])
                self.assertTrue('values' in roots[0])  # A
                self.assertTrue('geo' in roots[0])  # geo made the trip
                self.assertTrue('value' in roots[1])   # CAA
                self.assertTrue('values' in roots[2])  # SSHFP

                # these are stored as plural 'values'
                self.assertTrue('values' in data.pop('_srv._tcp'))
                self.assertTrue('values' in data.pop('mx'))
                self.assertTrue('values' in data.pop('naptr'))
                self.assertTrue('values' in data.pop('sub'))
                self.assertTrue('values' in data.pop('txt'))
                # these are stored as singular 'value'
                self.assertTrue('value' in data.pop('aaaa'))
                self.assertTrue('value' in data.pop('cname'))
                self.assertTrue('value' in data.pop('included'))
                self.assertTrue('value' in data.pop('ptr'))
                self.assertTrue('value' in data.pop('spf'))
                self.assertTrue('value' in data.pop('www'))
                self.assertTrue('value' in data.pop('www.sub'))

                # make sure nothing is left
                self.assertEquals([], data.keys())

            with open(dynamic_yaml_file) as fh:
                data = safe_load(fh.read())

                # make sure new dynamic records made the trip
                dyna = data.pop('a')
                self.assertTrue('values' in dyna)
                # self.assertTrue('dynamic' in dyna)
                # TODO:

                # make sure new dynamic records made the trip
                dyna = data.pop('aaaa')
                self.assertTrue('values' in dyna)
                # self.assertTrue('dynamic' in dyna)

                dyna = data.pop('cname')
                self.assertTrue('value' in dyna)
                # self.assertTrue('dynamic' in dyna)

                dyna = data.pop('simple-weighted')
                self.assertTrue('value' in dyna)
                # self.assertTrue('dynamic' in dyna)

                # make sure nothing is left
                self.assertEquals([], data.keys())

    def test_empty(self):
        source = YamlProvider('test', join(dirname(__file__), 'config'))

        zone = Zone('empty.', [])

        # without it we see everything
        source.populate(zone)
        self.assertEquals(0, len(zone.records))

    def test_unsorted(self):
        source = YamlProvider('test', join(dirname(__file__), 'config'))

        zone = Zone('unordered.', [])

        with self.assertRaises(ConstructorError):
            source.populate(zone)

        source = YamlProvider('test', join(dirname(__file__), 'config'),
                              enforce_order=False)
        # no exception
        source.populate(zone)
        self.assertEqual(2, len(zone.records))

    def test_subzone_handling(self):
        source = YamlProvider('test', join(dirname(__file__), 'config'))

        # If we add `sub` as a sub-zone we'll reject `www.sub`
        zone = Zone('unit.tests.', ['sub'])
        with self.assertRaises(SubzoneRecordException) as ctx:
            source.populate(zone)
        self.assertEquals('Record www.sub.unit.tests. is under a managed '
                          'subzone', ctx.exception.message)
