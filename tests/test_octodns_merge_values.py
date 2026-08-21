#
#
#
#

from unittest import TestCase

from octodns.merge import CaaMerger, MergerRegistry, TxtMerger
from octodns.merge.base import REGISTRY, BaseMerger
from octodns.record import Record
from octodns.record.exception import RecordException
from octodns.zone import Zone


class TestMergeValues(TestCase):
    zone = Zone('unit.tests.', [])

    def _caa(self, name, values):
        return Record.new(
            self.zone, name, {'ttl': 300, 'type': 'CAA', 'values': values}
        )

    def _txt(self, name, values):
        return Record.new(
            self.zone, name, {'ttl': 300, 'type': 'TXT', 'values': values}
        )

    def test_caa_same_tag_union(self):
        existing = self._caa(
            'caa', [{'flags': 0, 'tag': 'issue', 'value': 'letsencrypt.org'}]
        )
        incoming = self._caa(
            'caa', [{'flags': 0, 'tag': 'issue', 'value': 'digicert.com'}]
        )
        merged = CaaMerger().merge(existing, incoming)

        self.assertIsNotNone(merged)
        self.assertEqual(
            sorted((v.tag, v.value) for v in merged.values),
            [('issue', 'digicert.com'), ('issue', 'letsencrypt.org')],
        )

    def test_caa_new_tag_union(self):
        existing = self._caa(
            'caa',
            [
                {'flags': 0, 'tag': 'issue', 'value': 'letsencrypt.org'},
                {'flags': 0, 'tag': 'issuewild', 'value': ''},
            ],
        )
        incoming = self._caa(
            'caa', [{'flags': 0, 'tag': 'issue', 'value': 'digicert.com'}]
        )
        merged = CaaMerger().merge(existing, incoming)

        self.assertIsNotNone(merged)
        self.assertEqual(
            sorted((v.tag, v.value) for v in merged.values),
            [
                ('issue', 'digicert.com'),
                ('issue', 'letsencrypt.org'),
                ('issuewild', ''),
            ],
        )

    def test_caa_disjoint_tags_merge(self):
        # different tags (issue vs issuewild) still merge into one record
        existing = self._caa(
            'caa', [{'flags': 0, 'tag': 'issue', 'value': 'a.com'}]
        )
        incoming = self._caa(
            'caa', [{'flags': 0, 'tag': 'issuewild', 'value': ''}]
        )
        merged = CaaMerger().merge(existing, incoming)

        self.assertIsNotNone(merged)
        self.assertEqual(
            sorted((v.tag, v.value) for v in merged.values),
            [('issue', 'a.com'), ('issuewild', '')],
        )

    def test_caa_dedup_same_flag_value(self):
        existing = self._caa(
            'caa', [{'flags': 0, 'tag': 'issue', 'value': 'a.com'}]
        )
        incoming = self._caa(
            'caa', [{'flags': 0, 'tag': 'issue', 'value': 'a.com'}]
        )
        merged = CaaMerger().merge(existing, incoming)

        self.assertIsNone(merged)

    def test_caa_differing_flags_kept(self):
        existing = self._caa(
            'caa', [{'flags': 0, 'tag': 'issue', 'value': 'a.com'}]
        )
        incoming = self._caa(
            'caa', [{'flags': 128, 'tag': 'issue', 'value': 'b.com'}]
        )
        merged = CaaMerger().merge(existing, incoming)

        self.assertIsNotNone(merged)
        self.assertEqual(
            sorted((v.flags, v.tag, v.value) for v in merged.values),
            [(0, 'issue', 'a.com'), (128, 'issue', 'b.com')],
        )

    def test_caa_type_guard(self):
        existing = self._txt('txt', ['foo'])
        incoming = self._txt('txt', ['bar'])
        # a TXT merger must not touch CAA records and vice versa
        self.assertIsNone(CaaMerger().merge(existing, incoming))
        self.assertIsNone(CaaMerger().merge(incoming, existing))

    def test_caa_no_merge_subset(self):
        # incoming fully present in existing -> nothing to merge
        existing = self._caa(
            'caa',
            [
                {'flags': 0, 'tag': 'issue', 'value': 'a.com'},
                {'flags': 0, 'tag': 'issue', 'value': 'b.com'},
            ],
        )
        incoming = self._caa(
            'caa', [{'flags': 0, 'tag': 'issue', 'value': 'a.com'}]
        )
        self.assertIsNone(CaaMerger().merge(existing, incoming))

    def test_caa_merged_record_metadata(self):
        existing = self._caa(
            'caa', [{'flags': 0, 'tag': 'issue', 'value': 'letsencrypt.org'}]
        )
        # give existing truthy octodns metadata so it survives the merge
        existing.octodns['source'] = 'keep-me'
        incoming = self._caa(
            'caa', [{'flags': 0, 'tag': 'issue', 'value': 'digicert.com'}]
        )
        # incoming ttl differs on purpose
        incoming.ttl = 42
        merged = CaaMerger().merge(existing, incoming)

        # ttl is kept from the existing record, not taken from the incoming one
        self.assertEqual(300, merged.ttl)
        # octodns metadata preserved from existing
        self.assertEqual('keep-me', merged.octodns['source'])
        # source taken from the incoming record
        self.assertEqual(incoming.source, merged.source)

    def test_merged_record_ttl_conflict_warns(self):
        existing = self._caa(
            'caa', [{'flags': 0, 'tag': 'issue', 'value': 'letsencrypt.org'}]
        )
        incoming = self._caa(
            'caa', [{'flags': 0, 'tag': 'issuewild', 'value': ''}]
        )
        incoming.ttl = 60  # differs from existing's 300
        with self.assertLogs('Merge', level='WARNING') as logs:
            merged = CaaMerger().merge(existing, incoming)
        self.assertTrue(any('differing TTLs' in line for line in logs.output))
        # existing TTL is kept, incoming TTL is ignored
        self.assertEqual(300, merged.ttl)

    def test_txt_union(self):
        existing = self._txt('txt', ['foo'])
        incoming = self._txt('txt', ['bar'])
        merged = TxtMerger().merge(existing, incoming)

        self.assertIsNotNone(merged)
        self.assertEqual(['bar', 'foo'], sorted(str(v) for v in merged.values))

    def test_txt_dedup(self):
        existing = self._txt('txt', ['foo'])
        incoming = self._txt('txt', ['foo'])
        self.assertIsNone(TxtMerger().merge(existing, incoming))

    def test_txt_type_guard(self):
        existing = self._caa(
            'caa', [{'flags': 0, 'tag': 'issue', 'value': 'a.com'}]
        )
        incoming = self._caa(
            'caa', [{'flags': 0, 'tag': 'issue', 'value': 'b.com'}]
        )
        self.assertIsNone(TxtMerger().merge(existing, incoming))

    def test_base_merge_returns_none(self):
        self.assertIsNone(BaseMerger().merge(None, None))


class TestMergerRegistry(TestCase):
    def setUp(self):
        # start from a clean registry to avoid cross-test contamination
        self.registry = MergerRegistry()

    def test_register_instance(self):
        self.registry.register(CaaMerger())
        self.assertIn('caa', self.registry)

    def test_register_requires_base(self):
        with self.assertRaises(RecordException) as ctx:
            self.registry.register(object())
        self.assertIn('must be a BaseMerger', str(ctx.exception))

    def test_register_uses_instance_id(self):
        merger = CaaMerger()
        self.registry.register(merger)
        self.assertIs(merger, self.registry['caa'])

    def test_register_requires_non_empty_id(self):
        merger = BaseMerger()
        with self.assertRaises(ValueError) as ctx:
            self.registry.register(merger, id='')
        self.assertIn('non-empty id', str(ctx.exception))

    def test_register_duplicate_raises(self):
        self.registry.register(CaaMerger())
        with self.assertRaises(RecordException) as ctx:
            self.registry.register(CaaMerger())
        self.assertIn('already registered', str(ctx.exception))

    def test_register_duplicate_replace(self):
        self.registry.register(CaaMerger())
        other = CaaMerger()
        # same id, replace=True swaps it in
        self.registry.register(other, replace=True)
        self.assertIs(other, self.registry['caa'])

    def test_enable_unknown(self):
        with self.assertRaises(RecordException) as ctx:
            self.registry.enable('nope')
        self.assertIn('Unknown merger', str(ctx.exception))

    def test_enable_existing(self):
        self.registry.register(CaaMerger())
        # enabling an already-registered id is a no-op, no exception
        self.registry.enable('caa')
        self.assertIn('caa', self.registry)

    def test_disable_unknown(self):
        with self.assertRaises(RecordException) as ctx:
            self.registry.disable('nope')
        self.assertIn('Unknown merger', str(ctx.exception))

    def test_disable_existing(self):
        self.registry.register(CaaMerger())
        merged = self.registry.disable('caa')
        self.assertIsInstance(merged, CaaMerger)
        self.assertNotIn('caa', self.registry)

    def test_available(self):
        self.registry.register(CaaMerger())
        self.assertEqual({'caa': 'CaaMerger'}, self.registry.available())

    def test_container_protocol(self):
        self.registry.register(CaaMerger())
        self.registry.register(TxtMerger())
        self.assertEqual(2, len(self.registry))
        self.assertEqual({'caa', 'txt'}, set(self.registry))

    def test_merge_fold_produces(self):
        self.registry.register(CaaMerger())
        zone = Zone('unit.tests.', [])
        existing = Record.new(
            zone,
            'caa',
            {
                'ttl': 300,
                'type': 'CAA',
                'values': [
                    {'flags': 0, 'tag': 'issue', 'value': 'letsencrypt.org'}
                ],
            },
        )
        incoming = Record.new(
            zone,
            'caa',
            {
                'ttl': 300,
                'type': 'CAA',
                'values': [
                    {'flags': 0, 'tag': 'issue', 'value': 'digicert.com'}
                ],
            },
        )
        merged = self.registry.merge([CaaMerger()], existing, incoming)
        self.assertIsNotNone(merged)
        self.assertEqual(
            sorted((v.tag, v.value) for v in merged.values),
            [('issue', 'digicert.com'), ('issue', 'letsencrypt.org')],
        )

    def test_merge_fold_no_produce(self):
        # no merger produces a merge -> None
        zone = Zone('unit.tests.', [])
        existing = Record.new(
            zone,
            'caa',
            {
                'ttl': 300,
                'type': 'CAA',
                'values': [{'flags': 0, 'tag': 'issue', 'value': 'a.com'}],
            },
        )
        incoming = Record.new(
            zone,
            'caa',
            {
                'ttl': 300,
                'type': 'CAA',
                'values': [{'flags': 0, 'tag': 'issuewild', 'value': ''}],
            },
        )
        # TxtMerger doesn't handle CAA, so nothing merges
        self.assertIsNone(
            self.registry.merge([TxtMerger()], existing, incoming)
        )

    def test_merge_fold_empty(self):
        zone = Zone('unit.tests.', [])
        existing = Record.new(
            zone,
            'caa',
            {
                'ttl': 300,
                'type': 'CAA',
                'values': [{'flags': 0, 'tag': 'issue', 'value': 'a.com'}],
            },
        )
        incoming = Record.new(
            zone,
            'caa',
            {
                'ttl': 300,
                'type': 'CAA',
                'values': [{'flags': 0, 'tag': 'issue', 'value': 'b.com'}],
            },
        )
        self.assertIsNone(self.registry.merge([], existing, incoming))

    def test_merge_fold_accumulates(self):
        # each merger sees the accumulated record; TXT merger passes CAA
        # through unchanged while CAA merges
        zone = Zone('unit.tests.', [])
        existing = Record.new(
            zone,
            'caa',
            {
                'ttl': 300,
                'type': 'CAA',
                'values': [
                    {'flags': 0, 'tag': 'issue', 'value': 'letsencrypt.org'}
                ],
            },
        )
        incoming = Record.new(
            zone,
            'caa',
            {
                'ttl': 300,
                'type': 'CAA',
                'values': [
                    {'flags': 0, 'tag': 'issue', 'value': 'digicert.com'}
                ],
            },
        )
        merged = self.registry.merge(
            [TxtMerger(), CaaMerger()], existing, incoming
        )
        self.assertIsNotNone(merged)
        self.assertEqual(
            sorted((v.tag, v.value) for v in merged.values),
            [('issue', 'digicert.com'), ('issue', 'letsencrypt.org')],
        )


class TestRegistrySingleton(TestCase):
    def test_builtins_registered(self):
        self.assertIn('caa', REGISTRY)
        self.assertIn('txt', REGISTRY)
        self.assertIsInstance(REGISTRY['caa'], CaaMerger)
        self.assertIsInstance(REGISTRY['txt'], TxtMerger)
