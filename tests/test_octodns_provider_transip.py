from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from os.path import dirname, join
from unittest import TestCase
from unittest.mock import Mock, patch

from octodns.provider.transip import (DNSEntry, TransipConfigException,
                                      TransipException,
                                      TransipNewZoneException, TransipProvider,
                                      parse_to_fqdn)
from octodns.provider.yaml import YamlProvider
from octodns.zone import Zone
from transip.exceptions import TransIPHTTPError


def make_mock():
    expected = Zone("unit.tests.", [])
    source = YamlProvider("test", join(dirname(__file__), "config"))
    source.populate(expected)

    dns_entries = []
    for record in expected.records:
        if record._type in TransipProvider.SUPPORTS:
            entries_for = getattr(
                TransipProvider, "_entries_for_{}".format(record._type)
            )

            # Root records have '@' as name
            name = record.name
            if name == "":
                name = TransipProvider.ROOT_RECORD

            dns_entries.extend(entries_for(name, record))

            # Add a non-supported type
            # so it triggers the "is supported" (transip.py:115) check and
            # give 100% code coverage
            dns_entries.append(
                DNSEntry("@", "3600", "BOGUS", "ns01.transip.nl.")
            )

    mock = Mock()
    mock.return_value.domains.get.return_value.dns.list.return_value = (
        dns_entries
    )
    return mock


def make_mock_empty():
    mock = Mock()
    mock.return_value.domains.get.return_value.dns.list.return_value = []
    return mock


def make_failing_mock(response_code):
    mock = Mock()
    mock.return_value.domains.get.side_effect = [
        TransIPHTTPError(str(response_code), response_code)
    ]
    return mock


class TestTransipProvider(TestCase):

    bogus_key = "-----BEGIN RSA PRIVATE KEY-----Z-----END RSA PRIVATE KEY-----"

    def make_expected(self):
        expected = Zone("unit.tests.", [])
        source = YamlProvider("test", join(dirname(__file__), "config"))
        source.populate(expected)
        return expected

    @patch("octodns.provider.transip.TransIP", make_mock())
    def test_init(self):
        with self.assertRaises(TransipConfigException) as ctx:
            TransipProvider("test", "unittest")

        self.assertEquals(
            "Missing `key` of `key_file` parameter in config",
            str(ctx.exception),
        )

        TransipProvider("test", "unittest", key=self.bogus_key)

        # Existence and content of the key is tested in the SDK on client call
        TransipProvider("test", "unittest", key_file="/fake/path")

    @patch("octodns.provider.transip.TransIP", make_failing_mock(401))
    def test_populate_unauthenticated(self):
        # Unhappy Plan - Not authenticated
        # Live test against API, will fail in an unauthorized error
        with self.assertRaises(TransipException):
            provider = TransipProvider("test", "unittest", self.bogus_key)
            zone = Zone("unit.tests.", [])
            provider.populate(zone, True)

    @patch("octodns.provider.transip.TransIP", make_failing_mock(404))
    def test_populate_new_zone_as_target(self):
        # Unhappy Plan - Zone does not exists
        # Will trigger an exception if provider is used as a target for a
        # non-existing zone
        with self.assertRaises(TransipNewZoneException):
            provider = TransipProvider("test", "unittest", self.bogus_key)
            zone = Zone("notfound.unit.tests.", [])
            provider.populate(zone, True)

    @patch("octodns.provider.transip.TransIP", make_mock())
    def test_populate_new_zone_not_target(self):
        # Happy Plan - Zone does not exists
        # Won't trigger an exception if provider is NOT used as a target for a
        # non-existing zone.
        provider = TransipProvider("test", "unittest", self.bogus_key)
        zone = Zone("notfound.unit.tests.", [])
        provider.populate(zone, False)

    @patch("octodns.provider.transip.TransIP", make_failing_mock(404))
    def test_populate_zone_does_not_exist(self):
        # Happy Plan - Zone does not exists
        # Won't trigger an exception if provider is NOT used as a target for a
        # non-existing zone.
        provider = TransipProvider("test", "unittest", self.bogus_key)
        zone = Zone("notfound.unit.tests.", [])
        provider.populate(zone, False)

    @patch("octodns.provider.transip.TransIP", make_mock())
    def test_populate_zone_exists_not_target(self):
        # Happy Plan - Populate with mockup records
        provider = TransipProvider("test", "unittest", self.bogus_key)
        zone = Zone("unit.tests.", [])
        exists = provider.populate(zone, False)
        self.assertTrue(exists, "populate should return True")

    @patch("octodns.provider.transip.TransIP", make_mock())
    def test_populate_zone_exists_as_target(self):
        # Happy Plan - Even if the zone has no records the zone should exist
        provider = TransipProvider("test", "unittest", self.bogus_key)
        zone = Zone("unit.tests.", [])
        exists = provider.populate(zone, True)
        self.assertTrue(exists, "populate should return True")

    @patch("octodns.provider.transip.TransIP", make_mock_empty())
    def test_plan(self):
        _expected = self.make_expected()

        # Test happy plan, only create
        provider = TransipProvider("test", "unittest", self.bogus_key)

        plan = provider.plan(_expected)

        self.assertIsNotNone(plan)
        self.assertEqual(15, plan.change_counts["Create"])
        self.assertEqual(0, plan.change_counts["Update"])
        self.assertEqual(0, plan.change_counts["Delete"])

    @patch("octodns.provider.transip.TransIP")
    def test_apply(self, client_mock):
        # Test happy flow. Create all supported records
        domain_mock = Mock()
        client_mock.return_value.domains.get.return_value = domain_mock
        domain_mock.dns.list.return_value = []
        provider = TransipProvider("test", "unittest", self.bogus_key)

        plan = provider.plan(self.make_expected())
        self.assertIsNotNone(plan)
        provider.apply(plan)

        domain_mock.dns.replace.assert_called_once()  # TODO: assert payload

    @patch("octodns.provider.transip.TransIP")
    def test_apply_failure_on_not_found(self, client_mock):
        # Test unhappy flow. Trigger 'not found error' in apply stage
        # This should normally not happen as populate will capture it first
        # but just in case.
        domain_mock = Mock()
        domain_mock.dns.list.return_value = []
        client_mock.return_value.domains.get.side_effect = [
            domain_mock,
            TransIPHTTPError("Not Found", 404),
        ]
        provider = TransipProvider("test", "unittest", self.bogus_key)

        plan = provider.plan(self.make_expected())

        with self.assertRaises(TransipException):
            provider.apply(plan)

    @patch("octodns.provider.transip.TransIP")
    def test_apply_failure_on_error(self, client_mock):
        # Test unhappy flow. Trigger a unrecoverable error while saving
        domain_mock = Mock()
        domain_mock.dns.list.return_value = []
        domain_mock.dns.replace.side_effect = [
            TransIPHTTPError("Not Found", 500)
        ]
        client_mock.return_value.domains.get.return_value = domain_mock
        provider = TransipProvider("test", "unittest", self.bogus_key)

        plan = provider.plan(self.make_expected())

        with self.assertRaises(TransipException):
            provider.apply(plan)


class TestParseFQDN(TestCase):
    def test_parse_fqdn(self):
        zone = Zone("unit.tests.", [])
        self.assertEquals("www.unit.tests.", parse_to_fqdn("www", zone))
        self.assertEquals(
            "www.unit.tests.", parse_to_fqdn("www.unit.tests.", zone)
        )
        self.assertEquals(
            "www.sub.sub.sub.unit.tests.",
            parse_to_fqdn("www.sub.sub.sub", zone),
        )
        self.assertEquals("unit.tests.", parse_to_fqdn("@", zone))
