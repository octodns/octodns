#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from unittest import TestCase

from octodns.record import ARecord, AaaaRecord, Create, Delete, Record, Update
from octodns.zone import DuplicateRecordException, InvalidNodeException, \
    SubzoneRecordException, Zone

from helpers import SimpleProvider


class TestZone(TestCase):

    def test_lowering(self):
        zone = Zone('UniT.TEsTs.', [])
        self.assertEquals('unit.tests.', zone.name)

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
            self.assertEquals(hostname, zone.hostname_from_fqdn(fqdn))

    def test_add_record(self):
        zone = Zone('unit.tests.', [])

        a = ARecord(zone, 'a', {'ttl': 42, 'value': '1.1.1.1'})
        b = ARecord(zone, 'b', {'ttl': 42, 'value': '1.1.1.1'})
        c = ARecord(zone, 'a', {'ttl': 43, 'value': '2.2.2.2'})

        zone.add_record(a)
        self.assertEquals(zone.records, set([a]))
        # Can't add record with same name & type
        with self.assertRaises(DuplicateRecordException) as ctx:
            zone.add_record(a)
        self.assertEquals('Duplicate record a.unit.tests., type A',
                          ctx.exception.message)
        self.assertEquals(zone.records, set([a]))

        # can add duplicate with replace=True
        zone.add_record(c, replace=True)
        self.assertEquals('2.2.2.2', list(zone.records)[0].values[0])

        # Can add dup name, with different type
        zone.add_record(b)
        self.assertEquals(zone.records, set([a, b]))

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
        self.assertEquals(after.records, set([a, c]))
        changes = before.changes(after, target)
        self.assertEquals(2, len(changes))
        for change in changes:
            if isinstance(change, Create):
                create = change
            elif isinstance(change, Delete):
                delete = change
        self.assertEquals(b, delete.existing)
        self.assertFalse(delete.new)
        self.assertEquals(c, create.new)
        self.assertFalse(create.existing)
        delete.__repr__()
        create.__repr__()

        after = Zone('unit.tests.', [])
        changed = ARecord(before, 'a', {'ttl': 42, 'value': '2.2.2.2'})
        after.add_record(changed)
        after.add_record(b)
        changes = before.changes(after, target)
        self.assertEquals(1, len(changes))
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
        self.assertEquals(1, len(changes))
        self.assertIsInstance(changes[0], Create)

        # Only delete the supported A, not the AAAA
        changes = desired.changes(current, NoAaaaProvider())
        self.assertEquals(1, len(changes))
        self.assertIsInstance(changes[0], Delete)

    def test_missing_dot(self):
        with self.assertRaises(Exception) as ctx:
            Zone('not.allowed', [])
        self.assertTrue('missing ending dot' in ctx.exception.message)

    def test_sub_zones(self):
        zone = Zone('unit.tests.', set(['sub', 'barred']))

        # NS for exactly the sub is allowed
        record = Record.new(zone, 'sub', {
            'ttl': 3600,
            'type': 'NS',
            'values': ['1.2.3.4.', '2.3.4.5.'],
        })
        zone.add_record(record)
        self.assertEquals(set([record]), zone.records)

        # non-NS for exactly the sub is rejected
        record = Record.new(zone, 'sub', {
            'ttl': 3600,
            'type': 'A',
            'values': ['1.2.3.4', '2.3.4.5'],
        })
        with self.assertRaises(SubzoneRecordException) as ctx:
            zone.add_record(record)
        self.assertTrue('not of type NS', ctx.exception.message)

        # NS for something below the sub is rejected
        record = Record.new(zone, 'foo.sub', {
            'ttl': 3600,
            'type': 'NS',
            'values': ['1.2.3.4.', '2.3.4.5.'],
        })
        with self.assertRaises(SubzoneRecordException) as ctx:
            zone.add_record(record)
        self.assertTrue('under a managed sub-zone', ctx.exception.message)

        # A for something below the sub is rejected
        record = Record.new(zone, 'foo.bar.sub', {
            'ttl': 3600,
            'type': 'A',
            'values': ['1.2.3.4', '2.3.4.5'],
        })
        with self.assertRaises(SubzoneRecordException) as ctx:
            zone.add_record(record)
        self.assertTrue('under a managed sub-zone', ctx.exception.message)

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

        # add a to cname
        zone = Zone('unit.tests.', [])
        zone.add_record(cname)
        with self.assertRaises(InvalidNodeException):
            zone.add_record(a)

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
