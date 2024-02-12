#
#
#

from os import makedirs, remove
from os.path import dirname, isdir, isfile, join
from shutil import rmtree
from unittest import TestCase

from helpers import TemporaryDirectory
from yaml import safe_load
from yaml.constructor import ConstructorError

from octodns.idna import idna_encode
from octodns.provider import ProviderException
from octodns.provider.yaml import SplitYamlProvider, YamlProvider
from octodns.record import Create, NsValue, Record, ValuesMixin
from octodns.zone import SubzoneRecordException, Zone


def touch(filename):
    open(filename, 'w').close()


class TestYamlProvider(TestCase):
    def test_provider(self):
        source = YamlProvider('test', join(dirname(__file__), 'config'))

        zone = Zone('unit.tests.', [])
        dynamic_zone = Zone('dynamic.tests.', [])

        # With target we don't add anything
        source.populate(zone, target=source)
        self.assertEqual(0, len(zone.records))

        # without it we see everything
        source.populate(zone)
        self.assertEqual(25, len(zone.records))

        source.populate(dynamic_zone)
        self.assertEqual(6, len(dynamic_zone.records))

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
            target = YamlProvider(
                'test', directory, supports_root_ns=False, strict_supports=False
            )

            # We add everything
            plan = target.plan(zone)
            self.assertEqual(
                22, len([c for c in plan.changes if isinstance(c, Create)])
            )
            self.assertFalse(isfile(yaml_file))

            # Now actually do it
            self.assertEqual(22, target.apply(plan))
            self.assertTrue(isfile(yaml_file))

            # Dynamic plan
            plan = target.plan(dynamic_zone)
            self.assertEqual(
                6, len([c for c in plan.changes if isinstance(c, Create)])
            )
            self.assertFalse(isfile(dynamic_yaml_file))
            # Apply it
            self.assertEqual(6, target.apply(plan))
            self.assertTrue(isfile(dynamic_yaml_file))

            # There should be no changes after the round trip
            reloaded = Zone('unit.tests.', [])
            target.populate(reloaded)
            self.assertDictEqual(
                {'included': ['test']},
                [x for x in reloaded.records if x.name == 'included'][
                    0
                ].octodns,
            )

            # manually copy over the root since it will have been ignored
            # when things were written out
            reloaded.add_record(zone.root_ns)

            self.assertFalse(zone.changes(reloaded, target=source))

            # A 2nd sync should still create everything
            plan = target.plan(zone)
            self.assertEqual(
                22, len([c for c in plan.changes if isinstance(c, Create)])
            )

            with open(yaml_file) as fh:
                data = safe_load(fh.read())

                # '' has some of both
                roots = sorted(data.pop(''), key=lambda r: r['type'])
                self.assertTrue('values' in roots[0])  # A
                self.assertTrue('geo' in roots[0])  # geo made the trip
                self.assertTrue('value' in roots[1])  # CAA
                self.assertTrue('values' in roots[2])  # SSHFP

                # these are stored as plural 'values'
                self.assertTrue('values' in data.pop('_srv._tcp'))
                self.assertTrue('values' in data.pop('mx'))
                self.assertTrue('values' in data.pop('naptr'))
                self.assertTrue('values' in data.pop('sub'))
                self.assertTrue('values' in data.pop('txt'))
                self.assertTrue('values' in data.pop('loc'))
                self.assertTrue('values' in data.pop('urlfwd'))
                self.assertTrue('values' in data.pop('sub.txt'))
                self.assertTrue('values' in data.pop('subzone'))
                # these are stored as singular 'value'
                self.assertTrue('value' in data.pop('_imap._tcp'))
                self.assertTrue('value' in data.pop('_pop3._tcp'))
                self.assertTrue('value' in data.pop('aaaa'))
                self.assertTrue('value' in data.pop('cname'))
                self.assertTrue('value' in data.pop('dname'))
                self.assertTrue('value' in data.pop('included'))
                self.assertTrue('value' in data.pop('ptr'))
                self.assertTrue('value' in data.pop('spf'))
                self.assertTrue('value' in data.pop('www'))
                self.assertTrue('value' in data.pop('www.sub'))

                # make sure nothing is left
                self.assertEqual([], list(data.keys()))

            with open(dynamic_yaml_file) as fh:
                data = safe_load(fh.read())

                # make sure dynamic records made the trip
                dyna = data.pop('a')
                self.assertTrue('values' in dyna)
                self.assertTrue('dynamic' in dyna)

                # make sure dynamic records made the trip
                dyna = data.pop('aaaa')
                self.assertTrue('values' in dyna)
                self.assertTrue('dynamic' in dyna)

                dyna = data.pop('cname')
                self.assertTrue('value' in dyna)
                self.assertTrue('dynamic' in dyna)

                dyna = data.pop('real-ish-a')
                self.assertTrue('values' in dyna)
                self.assertTrue('dynamic' in dyna)

                dyna = data.pop('simple-weighted')
                self.assertTrue('value' in dyna)
                self.assertTrue('dynamic' in dyna)

                dyna = data.pop('pool-only-in-fallback')
                self.assertTrue('value' in dyna)
                self.assertTrue('dynamic' in dyna)

                # make sure nothing is left
                self.assertEqual([], list(data.keys()))

    def test_idna(self):
        with TemporaryDirectory() as td:
            name = 'déjà.vu.'
            filename = f'{name}yaml'

            provider = YamlProvider('test', td.dirname)
            zone = Zone(idna_encode(name), [])

            # create a idna named file
            with open(join(td.dirname, idna_encode(filename)), 'w') as fh:
                fh.write(
                    '''---
'':
  type: A
  value: 1.2.3.4
# something in idna notation
xn--dj-kia8a:
  type: A
  value: 2.3.4.5
# something with utf-8
これはテストです:
  type: A
  value: 3.4.5.6
'''
                )

            # populates fine when there's just the idna version (as a fallback)
            provider.populate(zone)
            d = {r.name: r for r in zone.records}
            self.assertEqual(3, len(d))
            # verify that we loaded the expected records, including idna/utf-8
            # named ones
            self.assertEqual(['1.2.3.4'], d[''].values)
            self.assertEqual(['2.3.4.5'], d['xn--dj-kia8a'].values)
            self.assertEqual(['3.4.5.6'], d['xn--28jm5b5a8k5k8cra'].values)

            # create a utf8 named file (provider always writes utf-8 filenames
            plan = provider.plan(zone)
            provider.apply(plan)

            with open(join(td.dirname, filename), 'r') as fh:
                content = fh.read()
                # verify that the non-ascii records were written out in utf-8
                self.assertTrue('déjà:' in content)
                self.assertTrue('これはテストです:' in content)

            # does not allow both idna and utf8 named files
            with self.assertRaises(ProviderException) as ctx:
                provider.populate(zone)
            msg = str(ctx.exception)
            self.assertTrue('Both UTF-8' in msg)

    def test_empty(self):
        source = YamlProvider(
            'test', join(dirname(__file__), 'config'), supports_root_ns=False
        )

        zone = Zone('empty.', [])

        # without it we see everything
        source.populate(zone)
        self.assertEqual(0, len(zone.records))

    def test_unsorted(self):
        source = YamlProvider(
            'test', join(dirname(__file__), 'config'), supports_root_ns=False
        )

        zone = Zone('unordered.', [])

        with self.assertRaises(ConstructorError):
            source.populate(zone)

        source = YamlProvider(
            'test',
            join(dirname(__file__), 'config'),
            enforce_order=False,
            supports_root_ns=False,
        )
        # no exception
        source.populate(zone)
        self.assertEqual(2, len(zone.records))

    def test_subzone_handling(self):
        source = YamlProvider(
            'test', join(dirname(__file__), 'config'), supports_root_ns=False
        )

        # If we add `sub` as a sub-zone we'll reject `www.sub`
        zone = Zone('unit.tests.', ['sub'])
        with self.assertRaises(SubzoneRecordException) as ctx:
            source.populate(zone)
        msg = str(ctx.exception)
        self.assertTrue(
            msg.startswith(
                'Record www.sub.unit.tests. is under a managed subzone'
            )
        )
        self.assertTrue(msg.endswith('unit.tests.yaml, line 201, column 3'))

    def test_SUPPORTS(self):
        source = YamlProvider('test', join(dirname(__file__), 'config'))
        # make sure the provider supports all the registered types
        self.assertEqual(Record.registered_types().keys(), source.SUPPORTS)

        class YamlRecord(ValuesMixin, Record):
            _type = 'YAML'
            _value_type = NsValue

        # don't know anything about a yaml type
        self.assertTrue('YAML' not in source.SUPPORTS)
        # register it
        Record.register_type(YamlRecord)
        # when asked again we'll now include it in our list of supports
        self.assertTrue('YAML' in source.SUPPORTS)

    def test_supports(self):
        source = YamlProvider('test', join(dirname(__file__), 'config'))

        class DummyType(object):
            def __init__(self, _type):
                self._type = _type

        # No matter what we check it's always supported
        self.assertTrue(source.supports(DummyType(None)))
        self.assertTrue(source.supports(DummyType(42)))
        self.assertTrue(source.supports(DummyType('A')))
        self.assertTrue(source.supports(DummyType(source)))
        self.assertTrue(source.supports(DummyType(self)))

    def test_list_zones(self):
        # test of pre-existing config that lives on disk
        provider = YamlProvider('test', 'tests/config')
        self.assertEqual(
            [
                'dynamic.tests.',
                'sub.txt.unit.tests.',
                'subzone.unit.tests.',
                'unit.tests.',
            ],
            list(provider.list_zones()),
        )

        # some synthetic tests to explicitly exercise the full functionality
        with TemporaryDirectory() as td:
            directory = join(td.dirname)

            # noise
            touch(join(directory, 'README.txt'))
            # not a zone.name.yaml
            touch(join(directory, 'production.yaml'))
            # non-zone directories
            makedirs(join(directory, 'directory'))
            makedirs(join(directory, 'never.matches'))

            # basic yaml zone files
            touch(join(directory, 'unit.test.yaml'))
            touch(join(directory, 'sub.unit.test.yaml'))
            touch(join(directory, 'other.tld.yaml'))
            touch(join(directory, 'both.tld.yaml'))

            # split zones with .
            makedirs(join(directory, 'split.test.'))
            makedirs(join(directory, 'sub.split.test.'))
            makedirs(join(directory, 'other.split.'))
            makedirs(join(directory, 'both.tld.'))

            # split zones with .tst
            makedirs(join(directory, 'split-ext.test.tst'))
            makedirs(join(directory, 'sub.split-ext.test.tst'))
            makedirs(join(directory, 'other-ext.split.tst'))

            provider = YamlProvider('test', directory)

            # basic, should only find zone files
            self.assertEqual(
                ['both.tld.', 'other.tld.', 'sub.unit.test.', 'unit.test.'],
                list(provider.list_zones()),
            )

            # include stuff with . AND basic
            provider.split_extension = '.'
            self.assertEqual(
                [
                    'both.tld.',
                    'other.split.',
                    'other.tld.',
                    'split.test.',
                    'sub.split.test.',
                    'sub.unit.test.',
                    'unit.test.',
                ],
                list(provider.list_zones()),
            )

            # include stuff with .tst AND basic
            provider.split_extension = '.tst'
            self.assertEqual(
                [
                    'both.tld.',
                    'other-ext.split.',
                    'other.tld.',
                    'split-ext.test.',
                    'sub.split-ext.test.',
                    'sub.unit.test.',
                    'unit.test.',
                ],
                list(provider.list_zones()),
            )

            # only .tst
            provider.disable_zonefile = True
            self.assertEqual(
                ['other-ext.split.', 'split-ext.test.', 'sub.split-ext.test.'],
                list(provider.list_zones()),
            )

            # only . (and both zone)
            provider.split_extension = '.'
            self.assertEqual(
                ['both.tld.', 'other.split.', 'split.test.', 'sub.split.test.'],
                list(provider.list_zones()),
            )

    def test_split_sources(self):
        with TemporaryDirectory() as td:
            directory = join(td.dirname)

            provider = YamlProvider('test', directory, split_extension='.')

            zone = Zone('déjà.vu.', [])
            zone_utf8 = join(directory, f'{zone.decoded_name}')
            zone_idna = join(directory, f'{zone.name}')

            filenames = (
                '*.yaml',
                '.yaml',
                'www.yaml',
                f'${zone.decoded_name}yaml',
            )

            # create the utf8 zone dir
            makedirs(zone_utf8)
            # nothing in it so we should get nothing back
            self.assertEqual([], list(provider._split_sources(zone)))
            # create some record files
            for filename in filenames:
                touch(join(zone_utf8, filename))
            # make sure we see them
            expected = [join(zone_utf8, f) for f in sorted(filenames)]
            self.assertEqual(expected, sorted(provider._split_sources(zone)))

            # add a idna zone directory
            makedirs(zone_idna)
            for filename in filenames:
                touch(join(zone_idna, filename))
            with self.assertRaises(ProviderException) as ctx:
                list(provider._split_sources(zone))
            msg = str(ctx.exception)
            self.assertTrue('Both UTF-8' in msg)

            # delete the utf8 version
            rmtree(zone_utf8)
            expected = [join(zone_idna, f) for f in sorted(filenames)]
            self.assertEqual(expected, sorted(provider._split_sources(zone)))

    def test_zone_sources(self):
        with TemporaryDirectory() as td:
            directory = join(td.dirname)

            provider = YamlProvider('test', directory)

            zone = Zone('déjà.vu.', [])
            utf8 = join(directory, f'{zone.decoded_name}yaml')
            idna = join(directory, f'{zone.name}yaml')

            # create the utf8 version
            touch(utf8)
            # make sure that's what we get back
            self.assertEqual(utf8, provider._zone_sources(zone))

            # create idna version, both exists
            touch(idna)
            with self.assertRaises(ProviderException) as ctx:
                provider._zone_sources(zone)
            msg = str(ctx.exception)
            self.assertTrue('Both UTF-8' in msg)

            # delete the utf8 version
            remove(utf8)
            # make sure that we get the idna one back
            self.assertEqual(idna, provider._zone_sources(zone))


class TestSplitYamlProvider(TestCase):
    def test_list_all_yaml_files(self):
        yaml_files = ('foo.yaml', '1.yaml', '$unit.tests.yaml')
        all_files = ('something', 'else', '1', '$$', '-f') + yaml_files
        all_dirs = ('dir1', 'dir2/sub', 'tricky.yaml')

        with TemporaryDirectory() as td:
            directory = join(td.dirname)

            # Create some files, some of them with a .yaml extension, all of
            # them empty.
            for emptyfile in all_files:
                touch(join(directory, emptyfile))
            # Do the same for some fake directories
            for emptydir in all_dirs:
                makedirs(join(directory, emptydir))

            # This isn't great, but given the variable nature of the temp dir
            # names, it's necessary.
            d = [join(directory, f) for f in yaml_files]
            self.assertEqual(len(yaml_files), len(d))

    def test_provider(self):
        source = SplitYamlProvider(
            'test',
            join(dirname(__file__), 'config/split'),
            extension='.tst',
            strict_supports=False,
        )

        zone = Zone('unit.tests.', [])
        dynamic_zone = Zone('dynamic.tests.', [])

        # With target we don't add anything
        source.populate(zone, target=source)
        self.assertEqual(0, len(zone.records))

        # without it we see everything
        source.populate(zone)
        self.assertEqual(20, len(zone.records))
        self.assertFalse([r for r in zone.records if r.name.startswith('only')])

        # temporarily enable zone file processing too, we should see one extra
        # record that came from unit.tests.
        source.disable_zonefile = False
        zone_both = Zone('unit.tests.', [])
        source.populate(zone_both)
        self.assertEqual(21, len(zone_both.records))
        n = len([r for r in zone_both.records if r.name == 'only-zone-file'])
        self.assertEqual(1, n)
        source.disable_zonefile = True

        # temporarily enable shared file processing, we should see one extra
        # record in the zone
        source.shared_filename = 'shared.yaml'
        zone_shared = Zone('unit.tests.', [])
        source.populate(zone_shared)
        self.assertEqual(21, len(zone_shared.records))
        n = len([r for r in zone_shared.records if r.name == 'only-shared'])
        self.assertEqual(1, n)
        dynamic_zone_shared = Zone('dynamic.tests.', [])
        source.populate(dynamic_zone_shared)
        self.assertEqual(6, len(dynamic_zone_shared.records))
        n = len(
            [r for r in dynamic_zone_shared.records if r.name == 'only-shared']
        )
        self.assertEqual(1, n)
        source.shared_filename = None

        source.populate(dynamic_zone)
        self.assertEqual(5, len(dynamic_zone.records))
        self.assertFalse(
            [r for r in dynamic_zone.records if r.name.startswith('only')]
        )

        with TemporaryDirectory() as td:
            # Add some subdirs to make sure that it can create them
            directory = join(td.dirname, 'sub', 'dir')
            zone_dir = join(directory, 'unit.tests.tst')
            dynamic_zone_dir = join(directory, 'dynamic.tests.tst')
            target = SplitYamlProvider(
                'test',
                directory,
                extension='.tst',
                supports_root_ns=False,
                strict_supports=False,
            )

            # We add everything
            plan = target.plan(zone)
            self.assertEqual(
                17, len([c for c in plan.changes if isinstance(c, Create)])
            )
            self.assertFalse(isdir(zone_dir))

            # Now actually do it
            self.assertEqual(17, target.apply(plan))

            # Dynamic plan
            plan = target.plan(dynamic_zone)
            self.assertEqual(
                5, len([c for c in plan.changes if isinstance(c, Create)])
            )
            self.assertFalse(isdir(dynamic_zone_dir))
            # Apply it
            self.assertEqual(5, target.apply(plan))
            self.assertTrue(isdir(dynamic_zone_dir))

            # There should be no changes after the round trip
            reloaded = Zone('unit.tests.', [])
            target.populate(reloaded)
            self.assertDictEqual(
                {'included': ['test']},
                [x for x in reloaded.records if x.name == 'included'][
                    0
                ].octodns,
            )

            # manually copy over the root since it will have been ignored
            # when things were written out
            reloaded.add_record(zone.root_ns)

            self.assertFalse(zone.changes(reloaded, target=source))

            # A 2nd sync should still create everything
            plan = target.plan(zone)
            self.assertEqual(
                17, len([c for c in plan.changes if isinstance(c, Create)])
            )

            yaml_file = join(zone_dir, '$unit.tests.yaml')
            self.assertTrue(isfile(yaml_file))
            with open(yaml_file) as fh:
                data = safe_load(fh.read())
                roots = sorted(data.pop(''), key=lambda r: r['type'])
                self.assertTrue('values' in roots[0])  # A
                self.assertTrue('geo' in roots[0])  # geo made the trip
                self.assertTrue('value' in roots[1])  # CAA
                self.assertTrue('values' in roots[2])  # SSHFP

            # These records are stored as plural "values." Check each file to
            # ensure correctness.
            for record_name in (
                '_srv._tcp',
                'mx',
                'naptr',
                'sub',
                'txt',
                'urlfwd',
            ):
                yaml_file = join(zone_dir, f'{record_name}.yaml')
                self.assertTrue(isfile(yaml_file))
                with open(yaml_file) as fh:
                    data = safe_load(fh.read())
                    self.assertTrue('values' in data.pop(record_name))

            # These are stored as singular "value." Again, check each file.
            for record_name in (
                'aaaa',
                'cname',
                'dname',
                'included',
                'ptr',
                'spf',
                'www.sub',
                'www',
            ):
                yaml_file = join(zone_dir, f'{record_name}.yaml')
                self.assertTrue(isfile(yaml_file))
                with open(yaml_file) as fh:
                    data = safe_load(fh.read())
                    self.assertTrue('value' in data.pop(record_name))

            # Again with the plural, this time checking dynamic.tests.
            for record_name in ('a', 'aaaa', 'real-ish-a'):
                yaml_file = join(dynamic_zone_dir, f'{record_name}.yaml')
                self.assertTrue(isfile(yaml_file))
                with open(yaml_file) as fh:
                    data = safe_load(fh.read())
                    dyna = data.pop(record_name)
                    self.assertTrue('values' in dyna)
                    self.assertTrue('dynamic' in dyna)

            # Singular again.
            for record_name in ('cname', 'simple-weighted'):
                yaml_file = join(dynamic_zone_dir, f'{record_name}.yaml')
                self.assertTrue(isfile(yaml_file))
                with open(yaml_file) as fh:
                    data = safe_load(fh.read())
                    dyna = data.pop(record_name)
                    self.assertTrue('value' in dyna)
                    self.assertTrue('dynamic' in dyna)

    def test_empty(self):
        source = SplitYamlProvider(
            'test', join(dirname(__file__), 'config/split'), extension='.tst'
        )

        zone = Zone('empty.', [])

        # without it we see everything
        with self.assertRaises(ProviderException):
            source.populate(zone)

    def test_unsorted(self):
        source = SplitYamlProvider(
            'test', join(dirname(__file__), 'config/split'), extension='.tst'
        )

        zone = Zone('unordered.', [])

        with self.assertRaises(ConstructorError):
            source.populate(zone)

        zone = Zone('unordered.', [])

        source = SplitYamlProvider(
            'test',
            join(dirname(__file__), 'config/split'),
            extension='.tst',
            enforce_order=False,
        )
        # no exception
        source.populate(zone)
        self.assertEqual(2, len(zone.records))

    def test_subzone_handling(self):
        source = SplitYamlProvider(
            'test', join(dirname(__file__), 'config/split'), extension='.tst'
        )

        # If we add `sub` as a sub-zone we'll reject `www.sub`
        zone = Zone('unit.tests.', ['sub'])
        with self.assertRaises(SubzoneRecordException) as ctx:
            source.populate(zone)
        msg = str(ctx.exception)
        self.assertTrue(
            msg.startswith(
                'Record www.sub.unit.tests. is under a managed subzone'
            )
        )
        self.assertTrue(msg.endswith('www.sub.yaml, line 3, column 3'))

    def test_copy(self):
        # going to put some sentinal values in here to ensure, these aren't
        # valid, but we shouldn't hit any code that cares during this test
        source = YamlProvider(
            'test',
            42,
            default_ttl=43,
            enforce_order=44,
            populate_should_replace=45,
            supports_root_ns=46,
        )
        copy = source.copy()
        self.assertEqual(source.directory, copy.directory)
        self.assertEqual(source.default_ttl, copy.default_ttl)
        self.assertEqual(source.enforce_order, copy.enforce_order)
        self.assertEqual(
            source.populate_should_replace, copy.populate_should_replace
        )
        self.assertEqual(source.supports_root_ns, copy.supports_root_ns)

        # same for split
        source = SplitYamlProvider(
            'test',
            42,
            extension=42.5,
            default_ttl=43,
            enforce_order=44,
            populate_should_replace=45,
            supports_root_ns=46,
        )
        copy = source.copy()
        self.assertEqual(source.directory, copy.directory)
        self.assertEqual(source.split_extension, copy.split_extension)
        self.assertEqual(source.default_ttl, copy.default_ttl)
        self.assertEqual(source.enforce_order, copy.enforce_order)
        self.assertEqual(
            source.populate_should_replace, copy.populate_should_replace
        )
        self.assertEqual(source.supports_root_ns, copy.supports_root_ns)

    def test_list_zones(self):
        provider = SplitYamlProvider(
            'test', 'tests/config/split', extension='.tst'
        )
        self.assertEqual(
            [
                'dynamic.tests.',
                'empty.',
                'subzone.unit.tests.',
                'unit.tests.',
                'unordered.',
            ],
            sorted(provider.list_zones()),
        )

    def test_hybrid_directory(self):
        source = YamlProvider(
            'test',
            join(dirname(__file__), 'config/hybrid'),
            split_extension='.',
            strict_supports=False,
        )

        # flat zone file only
        zone = Zone('one.test.', [])
        source.populate(zone)
        self.assertEqual(1, len(zone.records))

        # split zone only
        zone = Zone('two.test.', [])
        source.populate(zone)
        self.assertEqual(2, len(zone.records))


class TestOverridingYamlProvider(TestCase):
    def test_provider(self):
        config = join(dirname(__file__), 'config')
        override_config = join(dirname(__file__), 'config', 'override')
        base = YamlProvider(
            'base',
            config,
            populate_should_replace=False,
            supports_root_ns=False,
        )
        override = YamlProvider(
            'test',
            override_config,
            populate_should_replace=True,
            supports_root_ns=False,
        )

        zone = Zone('dynamic.tests.', [])

        # Load the base, should see the 5 records
        base.populate(zone)
        got = {r.name: r for r in zone.records}
        self.assertEqual(6, len(got))
        # We get the "dynamic" A from the base config
        self.assertTrue('dynamic' in got['a'].data)
        # No added
        self.assertFalse('added' in got)

        # Load the overrides, should replace one and add 1
        override.populate(zone)
        got = {r.name: r for r in zone.records}
        self.assertEqual(7, len(got))
        # 'a' was replaced with a generic record
        self.assertEqual(
            {'ttl': 3600, 'values': ['4.4.4.4', '5.5.5.5']}, got['a'].data
        )
        # And we have the new one
        self.assertTrue('added' in got)
