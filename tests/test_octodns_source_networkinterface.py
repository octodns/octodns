from unittest import TestCase
from unittest.mock import MagicMock

from ifaddr import IP

from octodns.source.networkinterface import NetworkInterfaceSource
from octodns.zone import Zone


class TestNetworkInterfaceSource(TestCase):
    def test_populate(self):
        name = 'testrecord'
        source = NetworkInterfaceSource('testid', name, is_loopback=True)
        source._get_ips = MagicMock(
            return_value=[IP('127.0.0.1', 0, ''), IP(('::1', 0, 0), 0, '')]
        )

        zone_name = 'unit.tests.'
        zone = Zone(zone_name, [])
        source.populate(zone)

        self.assertEqual(2, len(zone.records))

        a_record = list(
            filter(lambda record: record._type == 'A', zone.records)
        )[0]
        self.assertEqual(name, a_record.name)
        self.assertEqual(f'{name}.{zone_name}', a_record.fqdn)
        self.assertEqual(1, len(a_record.values))
        self.assertEqual('127.0.0.1', a_record.values[0])

        aaaa_record = list(
            filter(lambda record: record._type == 'AAAA', zone.records)
        )[0]
        self.assertEqual(name, aaaa_record.name)
        self.assertEqual(f'{name}.{zone_name}', aaaa_record.fqdn)
        self.assertEqual(1, len(aaaa_record.values))
        self.assertEqual('::1', aaaa_record.values[0])
