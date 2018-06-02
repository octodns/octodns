#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from os.path import dirname, isfile, join
from unittest import TestCase

from octodns.provider.etc_hosts import EtcHostsProvider
from octodns.provider.plan import Plan
from octodns.record import Record
from octodns.zone import Zone

from helpers import TemporaryDirectory


class TestEtcHostsProvider(TestCase):

    def test_provider(self):
        source = EtcHostsProvider('test', join(dirname(__file__), 'config'))

        zone = Zone('unit.tests.', [])

        # We never populate anything, when acting as a source
        source.populate(zone, target=source)
        self.assertEquals(0, len(zone.records))
        # Same if we're acting as a target
        source.populate(zone)
        self.assertEquals(0, len(zone.records))

        record = Record.new(zone, '', {
            'ttl': 60,
            'type': 'ALIAS',
            'value': 'www.unit.tests.'
        })
        zone.add_record(record)

        record = Record.new(zone, 'www', {
            'ttl': 60,
            'type': 'AAAA',
            'value': '2001:4860:4860::8888',
        })
        zone.add_record(record)
        record = Record.new(zone, 'www', {
            'ttl': 60,
            'type': 'A',
            'values': ['1.1.1.1', '2.2.2.2'],
        })
        zone.add_record(record)

        record = record.new(zone, 'v6', {
            'ttl': 60,
            'type': 'AAAA',
            'value': '2001:4860:4860::8844',
        })
        zone.add_record(record)

        record = record.new(zone, 'start', {
            'ttl': 60,
            'type': 'CNAME',
            'value': 'middle.unit.tests.',
        })
        zone.add_record(record)
        record = record.new(zone, 'middle', {
            'ttl': 60,
            'type': 'CNAME',
            'value': 'unit.tests.',
        })
        zone.add_record(record)

        record = record.new(zone, 'ext', {
            'ttl': 60,
            'type': 'CNAME',
            'value': 'github.com.',
        })
        zone.add_record(record)

        record = record.new(zone, '*', {
            'ttl': 60,
            'type': 'A',
            'value': '3.3.3.3',
        })
        zone.add_record(record)

        with TemporaryDirectory() as td:
            # Add some subdirs to make sure that it can create them
            directory = join(td.dirname, 'sub', 'dir')
            hosts_file = join(directory, 'unit.tests.hosts')
            target = EtcHostsProvider('test', directory)

            # We add everything
            plan = target.plan(zone)
            self.assertEquals(len(zone.records), len(plan.changes))
            self.assertFalse(isfile(hosts_file))

            # Now actually do it
            self.assertEquals(len(zone.records), target.apply(plan))
            self.assertTrue(isfile(hosts_file))

            with open(hosts_file) as fh:
                data = fh.read()
                # v6
                self.assertTrue('2001:4860:4860::8844\tv6.unit.tests')
                # www
                self.assertTrue('1.1.1.1\twww.unit.tests' in data)
                # root ALIAS
                self.assertTrue('# unit.tests -> www.unit.tests' in data)
                self.assertTrue('1.1.1.1\tunit.tests' in data)

                self.assertTrue('# start.unit.tests -> middle.unit.tests' in
                                data)
                self.assertTrue('# middle.unit.tests -> unit.tests' in data)
                self.assertTrue('# unit.tests -> www.unit.tests' in data)
                self.assertTrue('1.1.1.1	start.unit.tests' in data)

            # second empty run that won't create dirs and overwrites file
            plan = Plan(zone, zone, [], True)
            self.assertEquals(0, target.apply(plan))
