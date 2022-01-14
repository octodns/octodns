#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from unittest import TestCase

from octodns.processor.filter import TypeAllowlistFilter, TypeRejectlistFilter
from octodns.record import Record
from octodns.zone import Zone

zone = Zone('unit.tests.', [])
for record in [
    Record.new(zone, 'a', {
        'ttl': 30,
        'type': 'A',
        'value': '1.2.3.4',
    }),
    Record.new(zone, 'aaaa', {
        'ttl': 30,
        'type': 'AAAA',
        'value': '::1',
    }),
    Record.new(zone, 'txt', {
        'ttl': 30,
        'type': 'TXT',
        'value': 'Hello World!',
    }),
    Record.new(zone, 'a2', {
        'ttl': 30,
        'type': 'A',
        'value': '2.3.4.5',
    }),
    Record.new(zone, 'txt2', {
        'ttl': 30,
        'type': 'TXT',
        'value': 'That will do',
    }),
]:
    zone.add_record(record)


class TestTypeAllowListFilter(TestCase):

    def test_basics(self):
        filter_a = TypeAllowlistFilter('only-a', set(('A')))

        got = filter_a.process_source_zone(zone.copy())
        self.assertEqual(['a', 'a2'], sorted([r.name for r in got.records]))

        filter_aaaa = TypeAllowlistFilter('only-aaaa', ('AAAA',))
        got = filter_aaaa.process_source_zone(zone.copy())
        self.assertEqual(['aaaa'], sorted([r.name for r in got.records]))

        filter_txt = TypeAllowlistFilter('only-txt', ['TXT'])
        got = filter_txt.process_target_zone(zone.copy())
        self.assertEqual(['txt', 'txt2'],
                         sorted([r.name for r in got.records]))

        filter_a_aaaa = TypeAllowlistFilter('only-aaaa', set(('A', 'AAAA')))
        got = filter_a_aaaa.process_target_zone(zone.copy())
        self.assertEqual(['a', 'a2', 'aaaa'],
                         sorted([r.name for r in got.records]))


class TestTypeRejectListFilter(TestCase):

    def test_basics(self):
        filter_a = TypeRejectlistFilter('not-a', set(('A')))

        got = filter_a.process_source_zone(zone.copy())
        self.assertEqual(['aaaa', 'txt', 'txt2'],
                         sorted([r.name for r in got.records]))

        filter_aaaa = TypeRejectlistFilter('not-aaaa', ('AAAA',))
        got = filter_aaaa.process_source_zone(zone.copy())
        self.assertEqual(['a', 'a2', 'txt', 'txt2'],
                         sorted([r.name for r in got.records]))

        filter_txt = TypeRejectlistFilter('not-txt', ['TXT'])
        got = filter_txt.process_target_zone(zone.copy())
        self.assertEqual(['a', 'a2', 'aaaa'],
                         sorted([r.name for r in got.records]))

        filter_a_aaaa = TypeRejectlistFilter('not-a-aaaa', set(('A', 'AAAA')))
        got = filter_a_aaaa.process_target_zone(zone.copy())
        self.assertEqual(['txt', 'txt2'],
                         sorted([r.name for r in got.records]))
