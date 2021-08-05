#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from unittest import TestCase

from octodns.processor.acme import AcmeIgnoringProcessor
from octodns.record import Record
from octodns.zone import Zone

zone = Zone('unit.tests.', [])
for record in [
    # Will be ignored
    Record.new(zone, '_acme-challenge', {
        'ttl': 30,
        'type': 'TXT',
        'value': 'magic bit',
    }),
    # Not TXT so will live
    Record.new(zone, '_acme-challenge.aaaa', {
        'ttl': 30,
        'type': 'AAAA',
        'value': '::1',
    }),
    # Will be ignored
    Record.new(zone, '_acme-challenge.foo', {
        'ttl': 30,
        'type': 'TXT',
        'value': 'magic bit',
    }),
    # Not acme-challenge so will live
    Record.new(zone, 'txt', {
        'ttl': 30,
        'type': 'TXT',
        'value': 'Hello World!',
    }),
]:
    zone.add_record(record)


class TestAcmeIgnoringProcessor(TestCase):

    def test_basics(self):
        acme = AcmeIgnoringProcessor('acme')

        got = acme.process_source_zone(zone)
        self.assertEquals(['_acme-challenge.aaaa', 'txt'],
                          sorted([r.name for r in got.records]))
