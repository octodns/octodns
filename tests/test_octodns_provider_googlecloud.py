#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from octodns.record import Create, Delete, Update, Record
from octodns.provider.googlecloud import GoogleCloudProvider

from octodns.zone import Zone
from octodns.provider.base import Plan, BaseProvider

from unittest import TestCase
from mock import Mock, patch, PropertyMock

zone = Zone(name='unit.tests.', sub_zones=[])
octo_records = []
octo_records.append(Record.new(zone, '', {
    'ttl': 0,
    'type': 'A',
    'values': ['1.2.3.4', '10.10.10.10']}))
octo_records.append(Record.new(zone, 'a', {
    'ttl': 1,
    'type': 'A',
    'values': ['1.2.3.4', '1.1.1.1']}))
octo_records.append(Record.new(zone, 'aa', {
    'ttl': 9001,
    'type': 'A',
    'values': ['1.2.4.3']}))
octo_records.append(Record.new(zone, 'aaa', {
    'ttl': 2,
    'type': 'A',
    'values': ['1.1.1.3']}))
octo_records.append(Record.new(zone, 'cname', {
    'ttl': 3,
    'type': 'CNAME',
    'value': 'a.unit.tests.'}))
octo_records.append(Record.new(zone, 'mx1', {
    'ttl': 3,
    'type': 'MX',
    'values': [{
        'priority': 10,
        'value': 'mx1.unit.tests.',
    }, {
        'priority': 20,
        'value': 'mx2.unit.tests.',
    }]}))
octo_records.append(Record.new(zone, 'mx2', {
    'ttl': 3,
    'type': 'MX',
    'values': [{
        'priority': 10,
        'value': 'mx1.unit.tests.',
    }]}))
octo_records.append(Record.new(zone, '', {
    'ttl': 4,
    'type': 'NS',
    'values': ['ns1.unit.tests.', 'ns2.unit.tests.']}))
octo_records.append(Record.new(zone, 'foo', {
    'ttl': 5,
    'type': 'NS',
    'value': 'ns1.unit.tests.'}))
octo_records.append(Record.new(zone, '_srv._tcp', {
    'ttl': 6,
    'type': 'SRV',
    'values': [{
        'priority': 10,
        'weight': 20,
        'port': 30,
        'target': 'foo-1.unit.tests.',
    }, {
        'priority': 12,
        'weight': 30,
        'port': 30,
        'target': 'foo-2.unit.tests.',
    }]}))
octo_records.append(Record.new(zone, '_srv2._tcp', {
    'ttl': 7,
    'type': 'SRV',
    'values': [{
        'priority': 12,
        'weight': 17,
        'port': 1,
        'target': 'srvfoo.unit.tests.',
    }]}))
octo_records.append(Record.new(zone, 'txt1', {
    'ttl': 8,
    'type': 'TXT',
    'value': 'txt singleton test'}))
octo_records.append(Record.new(zone, 'txt2', {
    'ttl': 9,
    'type': 'TXT',
    'values': ['txt multiple test', 'txt multiple test 2']}))
octo_records.append(Record.new(zone, 'naptr', {
    'ttl': 9,
    'type': 'NAPTR',
    'values': [{
        'order': 100,
        'preference': 10,
        'flags': 'S',
        'service': 'SIP+D2U',
        'regexp': "!^.*$!sip:customer-service@unit.tests!",
        'replacement': '_sip._udp.unit.tests.'
    }]}))
octo_records.append(Record.new(zone, 'caa', {
    'ttl': 9,
    'type': 'CAA',
    'value': {
        'flags': 0,
        'tag': 'issue',
        'value': 'ca.unit.tests',
    }}))
for record in octo_records:
    zone.add_record(record)

# This is the format which the google API likes.
resource_record_sets = [
    ('unit.tests.', u'A', 0, [u'1.2.3.4', u'10.10.10.10']),
    (u'a.unit.tests.', u'A', 1, [u'1.1.1.1', u'1.2.3.4']),
    (u'aa.unit.tests.', u'A', 9001, [u'1.2.4.3']),
    (u'aaa.unit.tests.', u'A', 2, [u'1.1.1.3']),
    (u'cname.unit.tests.', u'CNAME', 3, [u'a.unit.tests.']),
    (u'mx1.unit.tests.', u'MX', 3,
     [u'10 mx1.unit.tests.', u'20 mx2.unit.tests.']),
    (u'mx2.unit.tests.', u'MX', 3, [u'10 mx1.unit.tests.']),
    ('unit.tests.', u'NS', 4, [u'ns1.unit.tests.', u'ns2.unit.tests.']),
    (u'foo.unit.tests.', u'NS', 5, [u'ns1.unit.tests.']),
    (u'_srv._tcp.unit.tests.', u'SRV', 6,
     [u'10 20 30 foo-1.unit.tests.', u'12 30 30 foo-2.unit.tests.']),
    (u'_srv2._tcp.unit.tests.', u'SRV', 7, [u'12 17 1 srvfoo.unit.tests.']),
    (u'txt1.unit.tests.', u'TXT', 8, [u'txt singleton test']),
    (u'txt2.unit.tests.', u'TXT', 9,
     [u'txt multiple test', u'txt multiple test 2']),
    (u'naptr.unit.tests.', u'NAPTR', 9, [
        u'100 10 "S" "SIP+D2U" "!^.*$!sip:customer-service@unit.tests!"'
        u' _sip._udp.unit.tests.']),
    (u'caa.unit.tests.', u'CAA', 9, [u'0 issue ca.unit.tests'])
]


class DummyResourceRecordSet:
    def __init__(self, record_name, record_type, ttl, rrdatas):
        self.name = record_name
        self.record_type = record_type
        self.ttl = ttl
        self.rrdatas = rrdatas

    def __eq__(self, other):
        try:
            return self.name == other.name \
                and self.record_type == other.record_type \
                and self.ttl == other.ttl  \
                and sorted(self.rrdatas) == sorted(other.rrdatas)
        except:
            return False

    def __repr__(self):
        return "{} {} {} {!s}"\
            .format(self.name, self.record_type, self.ttl, self.rrdatas)

    def __hash__(self):
        return hash(repr(self))


class DummyGoogleCloudZone:
    def __init__(self, dns_name, name=""):
        self.dns_name = dns_name
        self.name = name

    def resource_record_set(self, *args):
        return DummyResourceRecordSet(*args)

    def list_resource_record_sets(self, *args):
        pass

    def create(self, *args, **kwargs):
        pass


class DummyIterator:
    """Returns a mock DummyIterator object to use in testing.
    This is because API calls for google cloud DNS, if paged, contains a
    "next_page_token", which can be used to grab a subsequent
    iterator with more results.

        :type return: DummyIterator
    """
    def __init__(self,  list_of_stuff, page_token=None):
        self.iterable = iter(list_of_stuff)
        self.next_page_token = page_token

    def __iter__(self):
        return self

    def next(self):
        return self.iterable.next()


class TestGoogleCloudProvider(TestCase):
    @patch('octodns.provider.googlecloud.dns')
    def _get_provider(*args):
        '''Returns a mock GoogleCloudProvider object to use in testing.

            :type return: GoogleCloudProvider
        '''
        return GoogleCloudProvider(id=1, project="mock")

    @patch('octodns.provider.googlecloud.dns')
    def test___init__(self, *_):
        self.assertIsInstance(GoogleCloudProvider(id=1,
                                                  credentials_file="test",
                                                  project="unit test"),
                              BaseProvider)

        self.assertIsInstance(GoogleCloudProvider(id=1),
                              BaseProvider)

    @patch('octodns.provider.googlecloud.time.sleep')
    @patch('octodns.provider.googlecloud.dns')
    def test__apply(self, *_):
        class DummyDesired:
            def __init__(self, name, changes):
                self.name = name
                self.changes = changes

        apply_z = Zone("unit.tests.", [])
        create_r = Record.new(apply_z, '', {
            'ttl': 0,
            'type': 'A',
            'values': ['1.2.3.4', '10.10.10.10']})
        delete_r = Record.new(apply_z, 'a', {
            'ttl': 1,
            'type': 'A',
            'values': ['1.2.3.4', '1.1.1.1']})
        update_existing_r = Record.new(apply_z, 'aa', {
            'ttl': 9001,
            'type': 'A',
            'values': ['1.2.4.3']})
        update_new_r = Record.new(apply_z, 'aa', {
            'ttl': 666,
            'type': 'A',
            'values': ['1.4.3.2']})

        gcloud_zone_mock = DummyGoogleCloudZone("unit.tests.", "unit-tests")
        status_mock = Mock()
        return_values_for_status = iter(
            ["pending"] * 11 + ['done', 'done'])
        type(status_mock).status = PropertyMock(
            side_effect=return_values_for_status.next)
        gcloud_zone_mock.changes = Mock(return_value=status_mock)

        provider = self._get_provider()
        provider.gcloud_client = Mock()
        provider._gcloud_zones = {"unit.tests.": gcloud_zone_mock}
        desired = Mock()
        desired.name = "unit.tests."
        changes = []
        changes.append(Create(create_r))
        changes.append(Delete(delete_r))
        changes.append(Update(existing=update_existing_r, new=update_new_r))

        provider.apply(Plan(
            existing=[update_existing_r, delete_r],
            desired=desired,
            changes=changes,
            exists=True
        ))

        calls_mock = gcloud_zone_mock.changes.return_value
        mocked_calls = []
        for mock_call in calls_mock.add_record_set.mock_calls:
            mocked_calls.append(mock_call[1][0])

        self.assertEqual(mocked_calls, [
            DummyResourceRecordSet(
                'unit.tests.', 'A', 0, ['1.2.3.4', '10.10.10.10']),
            DummyResourceRecordSet(
                'aa.unit.tests.', 'A', 666, ['1.4.3.2'])
        ])

        mocked_calls2 = []
        for mock_call in calls_mock.delete_record_set.mock_calls:
            mocked_calls2.append(mock_call[1][0])

        self.assertEqual(mocked_calls2, [
            DummyResourceRecordSet(
                'a.unit.tests.', 'A', 1, ['1.2.3.4', '1.1.1.1']),
            DummyResourceRecordSet(
                'aa.unit.tests.', 'A', 9001, ['1.2.4.3'])
        ])

        type(status_mock).status = "pending"

        with self.assertRaises(RuntimeError):
            provider.apply(Plan(
                existing=[update_existing_r, delete_r],
                desired=desired,
                changes=changes,
                exists=True
            ))

        unsupported_change = Mock()
        unsupported_change.__len__ = Mock(return_value=1)
        type_mock = Mock()
        type_mock._type = "A"
        unsupported_change.record = type_mock

        mock_plan = Mock()
        type(mock_plan).desired = PropertyMock(return_value=DummyDesired(
            "dummy name", []))
        type(mock_plan).changes = [unsupported_change]

        with self.assertRaises(RuntimeError):
            provider.apply(mock_plan)

    def test__get_gcloud_client(self):
        provider = self._get_provider()

        self.assertIsInstance(provider, GoogleCloudProvider)

    @patch('octodns.provider.googlecloud.dns')
    def test_populate(self, _):
        def _get_mock_zones(page_token=None):
            if not page_token:
                return DummyIterator([
                    DummyGoogleCloudZone('example.com.'),
                ], page_token="MOCK_PAGE_TOKEN")
            elif page_token == "MOCK_PAGE_TOKEN":
                return DummyIterator([
                    DummyGoogleCloudZone('example2.com.'),
                ], page_token="MOCK_PAGE_TOKEN2")

            return DummyIterator([
                google_cloud_zone
            ])

        def _get_mock_record_sets(page_token=None):
            if not page_token:
                return DummyIterator(
                    [DummyResourceRecordSet(*v) for v in
                     resource_record_sets[:3]], page_token="MOCK_PAGE_TOKEN")
            elif page_token == "MOCK_PAGE_TOKEN":

                return DummyIterator(
                    [DummyResourceRecordSet(*v) for v in
                     resource_record_sets[3:5]], page_token="MOCK_PAGE_TOKEN2")
            return DummyIterator(
                [DummyResourceRecordSet(*v) for v in resource_record_sets[5:]])

        google_cloud_zone = DummyGoogleCloudZone('unit.tests.')

        provider = self._get_provider()
        provider.gcloud_client.list_zones = Mock(side_effect=_get_mock_zones)
        google_cloud_zone.list_resource_record_sets = Mock(
            side_effect=_get_mock_record_sets)

        self.assertEqual(provider.gcloud_zones.get("unit.tests.").dns_name,
                         "unit.tests.")

        test_zone = Zone('unit.tests.', [])
        exists = provider.populate(test_zone)
        self.assertTrue(exists)

        # test_zone gets fed the same records as zone does, except it's in
        # the format returned by google API, so after populate they should look
        # exactly the same.
        self.assertEqual(test_zone.records, zone.records)

        test_zone2 = Zone('nonexistent.zone.', [])
        exists = provider.populate(test_zone2, False, False)
        self.assertFalse(exists)

        self.assertEqual(len(test_zone2.records), 0,
                         msg="Zone should not get records from wrong domain")

        provider.SUPPORTS = set()
        test_zone3 = Zone('unit.tests.', [])
        provider.populate(test_zone3)
        self.assertEqual(len(test_zone3.records), 0)

    @patch('octodns.provider.googlecloud.dns')
    def test_populate_corner_cases(self, _):
        provider = self._get_provider()
        test_zone = Zone('unit.tests.', [])
        not_same_fqdn = DummyResourceRecordSet(
            'unit.tests.gr', u'A', 0, [u'1.2.3.4']),

        provider._get_gcloud_records = Mock(
            side_effect=[not_same_fqdn])
        provider._gcloud_zones = {
            "unit.tests.": DummyGoogleCloudZone("unit.tests.", "unit-tests")}

        provider.populate(test_zone)

        self.assertEqual(len(test_zone.records), 1)

        self.assertEqual(test_zone.records.pop().fqdn,
                         u'unit.tests.gr.unit.tests.')

    def test__get_gcloud_zone(self):
        provider = self._get_provider()

        provider.gcloud_client = Mock()
        provider.gcloud_client.list_zones = Mock(
            return_value=DummyIterator([]))

        self.assertIsNone(provider.gcloud_zones.get("nonexistent.zone"),
                          msg="Check that nonexistent zones return None when"
                              "there's no create=True flag")

    def test__get_rrsets(self):
        provider = self._get_provider()
        dummy_gcloud_zone = DummyGoogleCloudZone("unit.tests")
        for octo_record in octo_records:
            _rrset_func = getattr(
                provider, '_rrset_for_{}'.format(octo_record._type))
            self.assertEqual(
                _rrset_func(dummy_gcloud_zone, octo_record).record_type,
                octo_record._type
            )

    def test__create_zone(self):
        provider = self._get_provider()

        provider.gcloud_client = Mock()
        provider.gcloud_client.list_zones = Mock(
            return_value=DummyIterator([]))

        mock_zone = provider._create_gcloud_zone("nonexistent.zone.mock")

        mock_zone.create.assert_called()
        provider.gcloud_client.zone.assert_called()

    def test__create_zone_ip6_arpa(self):
        def _create_dummy_zone(name, dns_name):
            return DummyGoogleCloudZone(name=name, dns_name=dns_name)

        provider = self._get_provider()

        provider.gcloud_client = Mock()
        provider.gcloud_client.zone = Mock(side_effect=_create_dummy_zone)

        mock_zone = \
            provider._create_gcloud_zone('0.0.0.0.8.b.d.0.1.0.0.2.ip6.arpa')

        self.assertRegexpMatches(mock_zone.name, '^[a-z][a-z0-9-]*[a-z0-9]$')
        self.assertEqual(len(mock_zone.name), 63)

    def test_semicolon_fixup(self):
        provider = self._get_provider()

        self.assertEquals({
            'values': ['abcd\\; ef\\;g', 'hij\\; klm\\;n']
        }, provider._data_for_TXT(
            DummyResourceRecordSet(
                'unit.tests.', 'TXT', 0, ['abcd; ef;g', 'hij\\; klm\\;n'])
        ))
