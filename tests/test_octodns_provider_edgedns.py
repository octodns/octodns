#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

# from mock import Mock, call
from os.path import dirname, join
from requests import HTTPError
from requests_mock import ANY, mock as requests_mock
from six import text_type
from unittest import TestCase

from octodns.record import Record
from octodns.provider.edgedns import AkamaiProvider
from octodns.provider.fastdns import AkamaiProvider as LegacyAkamaiProvider
from octodns.provider.yaml import YamlProvider
from octodns.zone import Zone


class TestEdgeDnsProvider(TestCase):
    expected = Zone('unit.tests.', [])
    source = YamlProvider('test', join(dirname(__file__), 'config'))
    source.populate(expected)

    # Our test suite differs a bit, add our NS and remove the simple one
    expected.add_record(Record.new(expected, 'under', {
        'ttl': 3600,
        'type': 'NS',
        'values': [
            'ns1.unit.tests.',
            'ns2.unit.tests.',
        ]
    }))
    for record in list(expected.records):
        if record.name == 'sub' and record._type == 'NS':
            expected._remove_record(record)
            break

    def test_populate(self):
        provider = AkamaiProvider("test", "secret", "akam.com", "atok", "ctok")

        # Bad Auth
        with requests_mock() as mock:
            mock.get(ANY, status_code=401, text='{"message": "Unauthorized"}')

            with self.assertRaises(Exception) as ctx:
                zone = Zone('unit.tests.', [])
                provider.populate(zone)

            self.assertEquals(401, ctx.exception.response.status_code)

        # general error
        with requests_mock() as mock:
            mock.get(ANY, status_code=502, text='Things caught fire')

            with self.assertRaises(HTTPError) as ctx:
                zone = Zone('unit.tests.', [])
                provider.populate(zone)
            self.assertEquals(502, ctx.exception.response.status_code)

        # Non-existant zone doesn't populate anything
        with requests_mock() as mock:
            mock.get(ANY, status_code=404,
                     text='{"message": "Domain `foo.bar` not found"}')

            zone = Zone('unit.tests.', [])
            provider.populate(zone)
            self.assertEquals(set(), zone.records)

        # No diffs == no changes
        with requests_mock() as mock:

            with open('tests/fixtures/edgedns-records.json') as fh:
                mock.get(ANY, text=fh.read())

            zone = Zone('unit.tests.', [])
            provider.populate(zone)
            self.assertEquals(16, len(zone.records))
            changes = self.expected.changes(zone, provider)
            self.assertEquals(0, len(changes))

        # 2nd populate makes no network calls/all from cache
        again = Zone('unit.tests.', [])
        provider.populate(again)
        self.assertEquals(16, len(again.records))

        # bust the cache
        del provider._zone_records[zone.name]

    def test_apply(self):
        provider = AkamaiProvider("test", "s", "akam.com", "atok", "ctok",
                                  "cid", "gid")

        # tests create update delete through previous state config json
        with requests_mock() as mock:

            with open('tests/fixtures/edgedns-records-prev.json') as fh:
                mock.get(ANY, text=fh.read())

            plan = provider.plan(self.expected)
            mock.post(ANY, status_code=201)
            mock.put(ANY, status_code=200)
            mock.delete(ANY, status_code=204)

            changes = provider.apply(plan)
            self.assertEquals(29, changes)

        # Test against a zone that doesn't exist yet
        with requests_mock() as mock:
            with open('tests/fixtures/edgedns-records-prev-other.json') as fh:
                mock.get(ANY, status_code=404)

            plan = provider.plan(self.expected)
            mock.post(ANY, status_code=201)
            mock.put(ANY, status_code=200)
            mock.delete(ANY, status_code=204)

            changes = provider.apply(plan)
            self.assertEquals(14, changes)

        # Test against a zone that doesn't exist yet, but gid not provided
        with requests_mock() as mock:
            with open('tests/fixtures/edgedns-records-prev-other.json') as fh:
                mock.get(ANY, status_code=404)
            provider = AkamaiProvider("test", "s", "akam.com", "atok", "ctok",
                                      "cid")
            plan = provider.plan(self.expected)
            mock.post(ANY, status_code=201)
            mock.put(ANY, status_code=200)
            mock.delete(ANY, status_code=204)

            changes = provider.apply(plan)
            self.assertEquals(14, changes)

        # Test against a zone that doesn't exist, but cid not provided

        with requests_mock() as mock:
            mock.get(ANY, status_code=404)

            provider = AkamaiProvider("test", "s", "akam.com", "atok", "ctok")
            plan = provider.plan(self.expected)
            mock.post(ANY, status_code=201)
            mock.put(ANY, status_code=200)
            mock.delete(ANY, status_code=204)

            try:
                changes = provider.apply(plan)
            except NameError as e:
                expected = "contractId not specified to create zone"
                self.assertEquals(text_type(e), expected)


class TestDeprecatedAkamaiProvider(TestCase):

    def test_equivilent(self):
        self.assertEquals(LegacyAkamaiProvider, AkamaiProvider)
