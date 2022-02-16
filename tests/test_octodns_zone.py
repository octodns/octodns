#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from unittest import TestCase

from octodns.record import ARecord, AaaaRecord, Create, Delete, NsRecord, \
    Record, Update
from octodns.zone import DuplicateRecordException, InvalidNodeException, \
    SubzoneRecordException, Zone

from helpers import SimpleProvider


class TestZone(TestCase):

    def test_lowering(self):
        zone = Zone('UniT.TEsTs.', [])
        self.assertEqual('unit.tests.', zone.name)

    def test_hostname_from_fqdn(self):
        zone = Zone('unit.tests.', [])
        for hostname, fqdn in (
            ('', 'unit.tests.'),
            ('', 'unit.tests'),
            ('foo', 'foo.unit.tests.'),
            ('foo', 'foo.unit.tests'),
            ('foo.bar', 'foo.bar.unit.tests.'),
            ('foo.bar', 'foo.bar.unit.tests'),
            ('foo.unit.tests', 'foo.unit.tests.unit.tests.'),
            ('foo.unit.tests', 'foo.unit.tests.unit.tests'),
        ):
            self.assertEqual(hostname, zone.hostname_from_fqdn(fqdn))

    def test_add_record(self):
        zone = Zone('unit.tests.', [])

        a = ARecord(zone, 'a', {'ttl': 42, 'value': '1.1.1.1'})
        b = ARecord(zone, 'b', {'ttl': 42, 'value': '1.1.1.1'})
        c = ARecord(zone, 'a', {'ttl': 43, 'value': '2.2.2.2'})

        zone.add_record(a)
        self.assertEqual(zone.records, set([a]))
        # Can't add record with same name & type
        with self.assertRaises(DuplicateRecordException) as ctx:
            zone.add_record(a)
        self.assertEqual('Duplicate record a.unit.tests., type A',
                         str(ctx.exception))
        self.assertEqual(zone.records, set([a]))

        # can add duplicate with replace=True
        zone.add_record(c, replace=True)
        self.assertEqual('2.2.2.2', list(zone.records)[0].values[0])

        # Can add dup name, with different type
        zone.add_record(b)
        self.assertEqual(zone.records, set([a, b]))

    def test_changes(self):
        before = Zone('unit.tests.', [])
        a = ARecord(before, 'a', {'ttl': 42, 'value': '1.1.1.1'})
        before.add_record(a)
        b = AaaaRecord(before, 'b', {'ttl': 42, 'value': '1:1:1::1'})
        before.add_record(b)

        after = Zone('unit.tests.', [])
        after.add_record(a)
        after.add_record(b)

        target = SimpleProvider()

        # before == after -> no changes
        self.assertFalse(before.changes(after, target))

        # add a record, delete a record -> [Delete, Create]
        c = ARecord(before, 'c', {'ttl': 42, 'value': '1.1.1.1'})
        after.add_record(c)
        after._remove_record(b)
        self.assertEqual(after.records, set([a, c]))
        changes = before.changes(after, target)
        self.assertEqual(2, len(changes))
        for change in changes:
            if isinstance(change, Create):
                create = change
            elif isinstance(change, Delete):
                delete = change
        self.assertEqual(b, delete.existing)
        self.assertFalse(delete.new)
        self.assertEqual(c, create.new)
        self.assertFalse(create.existing)
        delete.__repr__()
        create.__repr__()

        after = Zone('unit.tests.', [])
        changed = ARecord(before, 'a', {'ttl': 42, 'value': '2.2.2.2'})
        after.add_record(changed)
        after.add_record(b)
        changes = before.changes(after, target)
        self.assertEqual(1, len(changes))
        update = changes[0]
        self.assertIsInstance(update, Update)
        # Using changes here to get a full equality
        self.assertFalse(a.changes(update.existing, target))
        self.assertFalse(changed.changes(update.new, target))
        update.__repr__()

    def test_unsupporting(self):

        class NoAaaaProvider(object):
            id = 'no-aaaa'
            SUPPORTS_GEO = False
            SUPPORTS_DYNAMIC = False

            def supports(self, record):
                return record._type != 'AAAA'

        current = Zone('unit.tests.', [])

        desired = Zone('unit.tests.', [])
        a = ARecord(desired, 'a', {'ttl': 42, 'value': '1.1.1.1'})
        desired.add_record(a)
        aaaa = AaaaRecord(desired, 'b', {'ttl': 42, 'value': '1:1:1::1'})
        desired.add_record(aaaa)

        # Only create the supported A, not the AAAA
        changes = current.changes(desired, NoAaaaProvider())
        self.assertEqual(1, len(changes))
        self.assertIsInstance(changes[0], Create)

        # Only delete the supported A, not the AAAA
        changes = desired.changes(current, NoAaaaProvider())
        self.assertEqual(1, len(changes))
        self.assertIsInstance(changes[0], Delete)

    def test_missing_dot(self):
        with self.assertRaises(Exception) as ctx:
            Zone('not.allowed', [])
        self.assertTrue('missing ending dot' in str(ctx.exception))

    def test_sub_zones(self):

        # NS for exactly the sub is allowed
        zone = Zone('unit.tests.', set(['sub', 'barred']))
        record = Record.new(zone, 'sub', {
            'ttl': 3600,
            'type': 'NS',
            'values': ['1.2.3.4.', '2.3.4.5.'],
        })
        zone.add_record(record)
        self.assertEqual(set([record]), zone.records)

        # non-NS for exactly the sub is rejected
        zone = Zone('unit.tests.', set(['sub', 'barred']))
        record = Record.new(zone, 'sub', {
            'ttl': 3600,
            'type': 'A',
            'values': ['1.2.3.4', '2.3.4.5'],
        })
        with self.assertRaises(SubzoneRecordException) as ctx:
            zone.add_record(record)
        self.assertTrue('not of type NS', str(ctx.exception))
        # Can add it w/lenient
        zone.add_record(record, lenient=True)
        self.assertEqual(set([record]), zone.records)

        # NS for something below the sub is rejected
        zone = Zone('unit.tests.', set(['sub', 'barred']))
        record = Record.new(zone, 'foo.sub', {
            'ttl': 3600,
            'type': 'NS',
            'values': ['1.2.3.4.', '2.3.4.5.'],
        })
        with self.assertRaises(SubzoneRecordException) as ctx:
            zone.add_record(record)
        self.assertTrue('under a managed sub-zone', str(ctx.exception))
        # Can add it w/lenient
        zone.add_record(record, lenient=True)
        self.assertEqual(set([record]), zone.records)

        # A for something below the sub is rejected
        zone = Zone('unit.tests.', set(['sub', 'barred']))
        record = Record.new(zone, 'foo.bar.sub', {
            'ttl': 3600,
            'type': 'A',
            'values': ['1.2.3.4', '2.3.4.5'],
        })
        with self.assertRaises(SubzoneRecordException) as ctx:
            zone.add_record(record)
        self.assertTrue('under a managed sub-zone', str(ctx.exception))
        # Can add it w/lenient
        zone.add_record(record, lenient=True)
        self.assertEqual(set([record]), zone.records)

    def test_ignored_records(self):
        zone_normal = Zone('unit.tests.', [])
        zone_ignored = Zone('unit.tests.', [])
        zone_missing = Zone('unit.tests.', [])

        normal = Record.new(zone_normal, 'www', {
            'ttl': 60,
            'type': 'A',
            'value': '9.9.9.9',
        })
        zone_normal.add_record(normal)

        ignored = Record.new(zone_ignored, 'www', {
            'octodns': {
                'ignored': True
            },
            'ttl': 60,
            'type': 'A',
            'value': '9.9.9.9',
        })
        zone_ignored.add_record(ignored)

        provider = SimpleProvider()

        self.assertFalse(zone_normal.changes(zone_ignored, provider))
        self.assertTrue(zone_normal.changes(zone_missing, provider))

        self.assertFalse(zone_ignored.changes(zone_normal, provider))
        self.assertFalse(zone_ignored.changes(zone_missing, provider))

        self.assertTrue(zone_missing.changes(zone_normal, provider))
        self.assertFalse(zone_missing.changes(zone_ignored, provider))

    def test_cname_coexisting(self):
        zone = Zone('unit.tests.', [])
        a = Record.new(zone, 'www', {
            'ttl': 60,
            'type': 'A',
            'value': '9.9.9.9',
        })
        cname = Record.new(zone, 'www', {
            'ttl': 60,
            'type': 'CNAME',
            'value': 'foo.bar.com.',
        })

        # add cname to a
        zone.add_record(a)
        with self.assertRaises(InvalidNodeException):
            zone.add_record(cname)
        self.assertEqual(set([a]), zone.records)
        zone.add_record(cname, lenient=True)
        self.assertEqual(set([a, cname]), zone.records)

        # add a to cname
        zone = Zone('unit.tests.', [])
        zone.add_record(cname)
        with self.assertRaises(InvalidNodeException):
            zone.add_record(a)
        self.assertEqual(set([cname]), zone.records)
        zone.add_record(a, lenient=True)
        self.assertEqual(set([a, cname]), zone.records)

    def test_excluded_records(self):
        zone_normal = Zone('unit.tests.', [])
        zone_excluded = Zone('unit.tests.', [])
        zone_missing = Zone('unit.tests.', [])

        normal = Record.new(zone_normal, 'www', {
            'ttl': 60,
            'type': 'A',
            'value': '9.9.9.9',
        })
        zone_normal.add_record(normal)

        excluded = Record.new(zone_excluded, 'www', {
            'octodns': {
                'excluded': ['test']
            },
            'ttl': 60,
            'type': 'A',
            'value': '9.9.9.9',
        })
        zone_excluded.add_record(excluded)

        provider = SimpleProvider()

        self.assertFalse(zone_normal.changes(zone_excluded, provider))
        self.assertTrue(zone_normal.changes(zone_missing, provider))

        self.assertFalse(zone_excluded.changes(zone_normal, provider))
        self.assertFalse(zone_excluded.changes(zone_missing, provider))

        self.assertTrue(zone_missing.changes(zone_normal, provider))
        self.assertFalse(zone_missing.changes(zone_excluded, provider))

    def test_included_records(self):
        zone_normal = Zone('unit.tests.', [])
        zone_included = Zone('unit.tests.', [])
        zone_missing = Zone('unit.tests.', [])

        normal = Record.new(zone_normal, 'www', {
            'ttl': 60,
            'type': 'A',
            'value': '9.9.9.9',
        })
        zone_normal.add_record(normal)

        included = Record.new(zone_included, 'www', {
            'octodns': {
                'included': ['test']
            },
            'ttl': 60,
            'type': 'A',
            'value': '9.9.9.9',
        })
        zone_included.add_record(included)

        provider = SimpleProvider()

        self.assertFalse(zone_normal.changes(zone_included, provider))
        self.assertTrue(zone_normal.changes(zone_missing, provider))

        self.assertFalse(zone_included.changes(zone_normal, provider))
        self.assertTrue(zone_included.changes(zone_missing, provider))

        self.assertTrue(zone_missing.changes(zone_normal, provider))
        self.assertTrue(zone_missing.changes(zone_included, provider))

    def test_not_included_records(self):
        zone_normal = Zone('unit.tests.', [])
        zone_included = Zone('unit.tests.', [])
        zone_missing = Zone('unit.tests.', [])

        normal = Record.new(zone_normal, 'www', {
            'ttl': 60,
            'type': 'A',
            'value': '9.9.9.9',
        })
        zone_normal.add_record(normal)

        included = Record.new(zone_included, 'www', {
            'octodns': {
                'included': ['not-here']
            },
            'ttl': 60,
            'type': 'A',
            'value': '9.9.9.9',
        })
        zone_included.add_record(included)

        provider = SimpleProvider()

        self.assertFalse(zone_normal.changes(zone_included, provider))
        self.assertTrue(zone_normal.changes(zone_missing, provider))

        self.assertFalse(zone_included.changes(zone_normal, provider))
        self.assertFalse(zone_included.changes(zone_missing, provider))

        self.assertTrue(zone_missing.changes(zone_normal, provider))
        self.assertFalse(zone_missing.changes(zone_included, provider))

    def assertEqualNameAndValues(self, a, b):
        a = dict([(r.name, r.values[0]) for r in a])
        b = dict([(r.name, r.values[0]) for r in b])
        self.assertEqual(a, b)

    def test_copy(self):
        zone = Zone('unit.tests.', [])

        a = ARecord(zone, 'a', {'ttl': 42, 'value': '1.1.1.1'})
        zone.add_record(a)
        b = ARecord(zone, 'b', {'ttl': 42, 'value': '1.1.1.2'})
        zone.add_record(b)

        # Sanity check
        self.assertEqualNameAndValues(set((a, b)), zone.records)

        copy = zone.copy()
        # We have an origin set and it is the source/original zone
        self.assertEqual(zone, copy._origin)
        # Our records are zone's records to start (references)
        self.assertEqualNameAndValues(zone.records, copy.records)

        # If we try and change something that's already there we realize and
        # then get an error about a duplicate
        b_prime = ARecord(zone, 'b', {'ttl': 42, 'value': '1.1.1.3'})
        with self.assertRaises(DuplicateRecordException):
            copy.add_record(b_prime)
        self.assertIsNone(copy._origin)
        # Unchanged, straight copies
        self.assertEqualNameAndValues(zone.records, copy.records)

        # If we add with replace things will be realized and the record will
        # have changed
        copy = zone.copy()
        copy.add_record(b_prime, replace=True)
        self.assertIsNone(copy._origin)
        self.assertEqualNameAndValues(set((a, b_prime)), copy.records)

        # If we add another record, things are reliazed and it has been added
        copy = zone.copy()
        c = ARecord(zone, 'c', {'ttl': 42, 'value': '1.1.1.3'})
        copy.add_record(c)
        self.assertEqualNameAndValues(set((a, b, c)), copy.records)

        # If we remove a record, things are reliazed and it has been removed
        copy = zone.copy()
        copy.remove_record(a)
        self.assertEqualNameAndValues(set((b,)), copy.records)

        # Re-realizing is a noop
        copy = zone.copy()
        # Happens the first time
        self.assertTrue(copy.hydrate())
        # Doesn't the second
        self.assertFalse(copy.hydrate())

    def test_root_ns(self):
        zone = Zone('unit.tests.', [])

        a = ARecord(zone, 'a', {'ttl': 42, 'value': '1.1.1.1'})
        zone.add_record(a)
        # No root NS yet
        self.assertFalse(zone.root_ns)

        non_root_ns = NsRecord(zone, 'sub', {'ttl': 42, 'values': (
            'ns1.unit.tests.',
            'ns2.unit.tests.',
        )})
        zone.add_record(non_root_ns)
        # No root NS yet b/c this was a sub
        self.assertFalse(zone.root_ns)

        root_ns = NsRecord(zone, '', {'ttl': 42, 'values': (
            'ns3.unit.tests.',
            'ns4.unit.tests.',
        )})
        zone.add_record(root_ns)
        # Now we have a root NS
        self.assertEqual(root_ns, zone.root_ns)

        # make a copy, it has a root_ns
        copy = zone.copy()
        self.assertEqual(root_ns, copy.root_ns)

        # remove the root NS from it and we don't
        copy.remove_record(root_ns)
        self.assertFalse(copy.root_ns)

        # original still does though
        self.assertEqual(root_ns, zone.root_ns)

        # remove the A, still has root NS
        zone.remove_record(a)
        self.assertEqual(root_ns, zone.root_ns)

        # remove the sub NS, still has root NS
        zone.remove_record(non_root_ns)
        self.assertEqual(root_ns, zone.root_ns)

        # finally remove the root NS, no more
        zone.remove_record(root_ns)
        self.assertFalse(zone.root_ns)
