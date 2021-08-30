from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from operator import itemgetter
from os.path import dirname, join
from unittest import TestCase
from unittest.mock import Mock, patch

from octodns.provider.transip import (TransipConfigException, TransipException,
                                      TransipNewZoneException, TransipProvider,
                                      _entries_for, _parse_to_fqdn)
from octodns.provider.yaml import YamlProvider
from octodns.zone import Zone
from transip.exceptions import TransIPHTTPError


def make_expected():
    expected = Zone("unit.tests.", [])
    source = YamlProvider("test", join(dirname(__file__), "config"))
    source.populate(expected)
    return expected


def make_mock():
    zone = make_expected()

    # Turn Zone.records into TransIP DNSEntries
    api_entries = []
    for record in zone.records:
        if record._type in TransipProvider.SUPPORTS:
            # Root records have '@' as name
            name = record.name
            if name == "":
                name = TransipProvider.ROOT_RECORD

            api_entries.extend(_entries_for(name, record))

    return zone, api_entries


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

    @patch("octodns.provider.transip.TransIP", make_mock_empty())
    def test_init(self):
        with self.assertRaises(TransipConfigException) as ctx:
            TransipProvider("test", "unittest")

        self.assertEquals(
            "Missing `key` of `key_file` parameter in config",
            str(ctx.exception),
        )

        # Those should work
        TransipProvider("test", "unittest", key=self.bogus_key)
        TransipProvider("test", "unittest", key_file="/fake/path")

    @patch("octodns.provider.transip.TransIP", make_failing_mock(401))
    def test_populate_unauthenticated(self):
        # Unhappy Plan - Not authenticated
        provider = TransipProvider("test", "unittest", self.bogus_key)
        zone = Zone("unit.tests.", [])
        with self.assertRaises(TransipException):
            provider.populate(zone, True)

    @patch("octodns.provider.transip.TransIP", make_failing_mock(404))
    def test_populate_new_zone_as_target(self):
        # Unhappy Plan - Zone does not exists
        # Will trigger an exception if provider is used as a target for a
        # non-existing zone
        provider = TransipProvider("test", "unittest", self.bogus_key)
        zone = Zone("notfound.unit.tests.", [])
        with self.assertRaises(TransipNewZoneException):
            provider.populate(zone, True)

    @patch("octodns.provider.transip.TransIP", make_mock_empty())
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

    @patch("octodns.provider.transip.TransIP")
    def test_populate_zone_exists_not_target(self, mock_client):
        # Happy Plan - Populate
        source_zone, api_records = make_mock()
        mock_client.return_value.domains.get.return_value.dns.list.\
            return_value = api_records
        provider = TransipProvider("test", "unittest", self.bogus_key)
        zone = Zone("unit.tests.", [])

        exists = provider.populate(zone, False)

        self.assertTrue(exists, "populate should return True")

        # Due to the implementation of Record._equality_tuple() we can't do a
        # normal compare, as that ingores ttl's for example. We therefor use
        # the __repr__ to compare. We do need to filter out `.geo` attributes
        # that Transip doesn't support.
        expected = set()
        for r in source_zone.records:
            if r._type in TransipProvider.SUPPORTS:
                if hasattr(r, "geo"):
                    r.geo = None
                expected.add(r.__repr__())
        self.assertEqual({r.__repr__() for r in zone.records}, expected)

    @patch("octodns.provider.transip.TransIP", make_mock_empty())
    def test_populate_zone_exists_as_target(self):
        # Happy Plan - Even if the zone has no records the zone should exist
        provider = TransipProvider("test", "unittest", self.bogus_key)
        zone = Zone("unit.tests.", [])
        exists = provider.populate(zone, True)
        self.assertTrue(exists, "populate should return True")

    @patch("octodns.provider.transip.TransIP", make_mock_empty())
    def test_plan(self):
        # Test happy plan, only create
        provider = TransipProvider("test", "unittest", self.bogus_key)

        plan = provider.plan(make_expected())

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

        plan = provider.plan(make_expected())
        self.assertIsNotNone(plan)
        provider.apply(plan)

        domain_mock.dns.replace.assert_called_once()

        # These are the supported ones from tests/config/unit.test.yaml
        expected_entries = [
            {
                "name": "ignored",
                "expire": 3600,
                "type": "A",
                "content": "9.9.9.9",
            },
            {
                "name": "@",
                "expire": 3600,
                "type": "CAA",
                "content": "0 issue ca.unit.tests",
            },
            {
                "name": "sub",
                "expire": 3600,
                "type": "NS",
                "content": "6.2.3.4.",
            },
            {
                "name": "sub",
                "expire": 3600,
                "type": "NS",
                "content": "7.2.3.4.",
            },
            {
                "name": "spf",
                "expire": 600,
                "type": "SPF",
                "content": "v=spf1 ip4:192.168.0.1/16-all",
            },
            {
                "name": "_srv._tcp",
                "expire": 600,
                "type": "SRV",
                "content": "10 20 30 foo-1.unit.tests.",
            },
            {
                "name": "_srv._tcp",
                "expire": 600,
                "type": "SRV",
                "content": "12 20 30 foo-2.unit.tests.",
            },
            {
                "name": "_pop3._tcp",
                "expire": 600,
                "type": "SRV",
                "content": "0 0 0 .",
            },
            {
                "name": "_imap._tcp",
                "expire": 600,
                "type": "SRV",
                "content": "0 0 0 .",
            },
            {
                "name": "txt",
                "expire": 600,
                "type": "TXT",
                "content": "Bah bah black sheep",
            },
            {
                "name": "txt",
                "expire": 600,
                "type": "TXT",
                "content": "have you any wool.",
            },
            {
                "name": "txt",
                "expire": 600,
                "type": "TXT",
                "content": (
                    "v=DKIM1;k=rsa;s=email;h=sha256;"
                    "p=A/kinda+of/long/string+with+numb3rs"
                ),
            },
            {"name": "@", "expire": 3600, "type": "NS", "content": "6.2.3.4."},
            {"name": "@", "expire": 3600, "type": "NS", "content": "7.2.3.4."},
            {
                "name": "cname",
                "expire": 300,
                "type": "CNAME",
                "content": "unit.tests.",
            },
            {
                "name": "excluded",
                "expire": 3600,
                "type": "CNAME",
                "content": "unit.tests.",
            },
            {
                "name": "www.sub",
                "expire": 300,
                "type": "A",
                "content": "2.2.3.6",
            },
            {
                "name": "included",
                "expire": 3600,
                "type": "CNAME",
                "content": "unit.tests.",
            },
            {
                "name": "mx",
                "expire": 300,
                "type": "MX",
                "content": "10 smtp-4.unit.tests.",
            },
            {
                "name": "mx",
                "expire": 300,
                "type": "MX",
                "content": "20 smtp-2.unit.tests.",
            },
            {
                "name": "mx",
                "expire": 300,
                "type": "MX",
                "content": "30 smtp-3.unit.tests.",
            },
            {
                "name": "mx",
                "expire": 300,
                "type": "MX",
                "content": "40 smtp-1.unit.tests.",
            },
            {
                "name": "aaaa",
                "expire": 600,
                "type": "AAAA",
                "content": "2601:644:500:e210:62f8:1dff:feb8:947a",
            },
            {"name": "@", "expire": 300, "type": "A", "content": "1.2.3.4"},
            {"name": "@", "expire": 300, "type": "A", "content": "1.2.3.5"},
            {"name": "www", "expire": 300, "type": "A", "content": "2.2.3.6"},
            {
                "name": "@",
                "expire": 3600,
                "type": "SSHFP",
                "content": "1 1 7491973e5f8b39d5327cd4e08bc81b05f7710b49",
            },
            {
                "name": "@",
                "expire": 3600,
                "type": "SSHFP",
                "content": "1 1 bf6b6825d2977c511a475bbefb88aad54a92ac73",
            },
        ]
        # Unpack from the transip library magic structure...
        seen_entries = [
            e.__dict__["_attrs"]
            for e in domain_mock.dns.replace.mock_calls[0][1][0]
        ]
        self.assertEqual(
            sorted(seen_entries, key=itemgetter("name", "type", "expire")),
            sorted(expected_entries, key=itemgetter("name", "type", "expire")),
        )

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

        plan = provider.plan(make_expected())

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

        plan = provider.plan(make_expected())

        with self.assertRaises(TransipException):
            provider.apply(plan)


class TestParseFQDN(TestCase):
    def test_parse_fqdn(self):
        zone = Zone("unit.tests.", [])
        self.assertEquals("www.unit.tests.", _parse_to_fqdn("www", zone))
        self.assertEquals(
            "www.unit.tests.", _parse_to_fqdn("www.unit.tests.", zone)
        )
        self.assertEquals(
            "www.sub.sub.sub.unit.tests.",
            _parse_to_fqdn("www.sub.sub.sub", zone),
        )
        self.assertEquals("unit.tests.", _parse_to_fqdn("@", zone))
