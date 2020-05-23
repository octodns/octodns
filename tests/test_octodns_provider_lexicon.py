from unittest import TestCase

import mock
from mock import Mock

from octodns.provider.lexicon import LexiconProvider, \
    OnTheFlyLexiconConfigSource
from octodns.provider.plan import Plan
from octodns.record import Record, Create, Delete, Update
from octodns.zone import Zone

LEXICON_DATA = [
    {'type': 'A', 'name': '@.blodapels.in', 'ttl': 10800, 'content':
        '192.0.184.38', 'id': '@'},
    {'type': 'MX', 'name': '@.blodapels.in', 'ttl': 10800, 'content':
        '10 spool.mail.example.com.', 'id': '@'},
    {'type': 'MX', 'name': '@.blodapels.in', 'ttl': 10800, 'content':
        '50 fb.mail.example.com.', 'id': '@'},
    {'type': 'TXT', 'name': '@.blodapels.in', 'ttl': 10800, 'content':
        'v=spf1 include:_mailcust.example.com ?all',
     'id': '@'},
    {'type': 'CNAME', 'name': 'webmail.blodapels.in', 'ttl': 10800, 'content':
        'webmail.example.com.', 'id': 'webmail'},
    {'type': 'CNAME', 'name': 'www.blodapels.in', 'ttl': 10800, 'content':
        'webredir.vip.example.com.', 'id': 'www'},
    {'type': 'SRV', 'name': '_imap._tcp.blodapels.in', 'ttl': 10800,
     'content': '0 0 0   .', 'id': '_imap._tcp'},
    {'type': 'SRV', 'name': '_imaps._tcp.blodapels.in', 'ttl': 10800,
     'content': '0 1 993 mail.example.com.',
     'id': '_imaps._tcp'},
    {'type': 'SRV', 'name': '_pop3._tcp.blodapels.in', 'ttl': 10800,
     'content': '0 0 0   .', 'id': '_pop3._tcp'},
    {'type': 'SRV', 'name': '_pop3s._tcp.blodapels.in', 'ttl': 10800,
     'content': '10 1 995 mail.example.com.',
     'id': '_pop3s._tcp'},
    {'type': 'SRV', 'name': '_submission._tcp.blodapels.in', 'ttl': 10800,
     'content': '0 1 465 mail.example.com.',
     'id': '_submission._tcp'},
    {'type': 'URL', 'name': '@.id.example.com', 'ttl': '1800', 'content':
        'http://www.example.com/', 'id': '745514'},
    {'type': 'CAA', 'name': '@.blodapels.in', 'ttl': 10800, 'content':
        '0 issue ";"', 'id': '@'},
    {'type': 'CAA', 'name': '@.blodapels.in', 'ttl': 10800, 'content':
        '0 issuewild "letsencrypt.org"', 'id': '@'}
]

ZONE = Zone("blodapels.in.", [])

source = Mock()

OCTODNS_DATA = [
    Record.new(ZONE, '@', {'ttl': 10800, 'type': 'A',
                           'values': ['192.0.184.38']}, source=source),
    Record.new(ZONE, '@', {'ttl': 10800, 'type': 'MX',
                           'values': [{'priority': '10', 'exchange':
                                      'spool.mail.example.com.'},
                                      {'priority': '50', 'exchange':
                                          'fb.mail.example.com.'}]},
               source=source),
    Record.new(ZONE, '@', {'ttl': 10800, 'type': 'TXT',
                           'values':
                               ['v=spf1 include:_mailcust.example.com ?all']},
               source=source),
    Record.new(ZONE, 'webmail', {'ttl': 10800, 'type': 'CNAME', 'value':
                                 'webmail.example.com.'}, source=source),
    Record.new(ZONE, 'www', {'ttl': 10800, 'type': 'CNAME', 'value':
                             'webredir.vip.example.com.'}, source=source),
    Record.new(ZONE, '_imap._tcp',
               {'type': 'SRV', 'ttl': 10800, 'values':
                   [{'priority': '0', 'weight': '0', 'port': '0',
                     'target': '.'}]},
               source=source),
    Record.new(ZONE, '_imaps._tcp', {'type': 'SRV', 'ttl': 10800, 'values': [
        {'priority': '0', 'weight': '1', 'port': '993',
         'target': 'mail.example.com.'}]}, source=source),
    Record.new(ZONE, '_pop3._tcp',
               {'type': 'SRV', 'ttl': 10800, 'values': [
                   {'priority': '0', 'weight': '0', 'port': '0',
                    'target': '.'}]},
               source=source),
    Record.new(ZONE, '_pop3s._tcp', {'type': 'SRV', 'ttl': 10800, 'values': [
        {'priority': '10', 'weight': '1', 'port': '995',
         'target': 'mail.example.com.'}]}, source=source),
    Record.new(ZONE, '_submission._tcp',
               {'type': 'SRV', 'ttl': 10800, 'values': [
                   {'priority': '0', 'weight': '1', 'port': '465',
                    'target': 'mail.example.com.'}]}, source=source),
    Record.new(ZONE, '@',
               {'type': 'CAA', 'ttl': 10800, 'values': [
                   {'flags': 0, 'tag': 'issue', 'value': ';'},
                   {'flags': 0, 'tag': 'issuewild',
                    'value': 'letsencrypt.org'}]},
               source=source)
]

lexicon_config = {
    "provider_name": "gandi",
    "domain": 'blodapels.in',
    "gandi": {
        "api_protocol": "rest",
        "auth_token": "X"
    }
}


class TestLexiconProvider(TestCase):

    @mock.patch('lexicon.providers.gandi.Provider')
    def test_populate(self, mock_provider):
        # Given
        provider = LexiconProvider(id="unittests",
                                   lexicon_config=lexicon_config)
        zone = Zone("blodapels.in.", [])

        provider.lexicon_client.provider.list_records.side_effect \
            = lambda *s: iter(LEXICON_DATA)

        # When
        provider.populate(zone=zone)

        # Then
        self.assertEqual(zone.records, set(OCTODNS_DATA))
        self.assertTrue(mock_provider.called, "authenticate was called")

    @mock.patch('lexicon.providers.gandi.Provider')
    def test_populate_crash_on_unknown(self, _):
        # Given
        provider = LexiconProvider(id="unittests",
                                   raise_on_unhandled=True,
                                   lexicon_config=lexicon_config)
        zone = Zone("blodapels.in.", [])

        provider.lexicon_client.provider.list_records.side_effect \
            = lambda *s: iter(LEXICON_DATA)

        with self.assertRaises(RuntimeError):
            provider.populate(zone=zone)

    @mock.patch('lexicon.providers.gandi.Provider')
    def test_populate_with_relative_name(self, _):
        # Given
        lexicon_data = [{'type': 'A',
                         'name': '@',
                         'ttl': 10800,
                         'content': '192.0.184.38',
                         'id': '@'}]
        provider = LexiconProvider(id="unittests",
                                   lexicon_config=lexicon_config)
        zone = Zone("blodapels.in.", [])

        expected_record = Record.new(ZONE, '@', {'ttl': 10800, 'type': 'A',
                                                 'values': ['192.0.184.38']},
                                     source=source)

        provider.lexicon_client.provider.list_records.side_effect \
            = lambda *s: iter(lexicon_data)

        # When
        provider.populate(zone)

        # Then
        self.assertEqual(zone.records, {expected_record},
                         "relative names from list are handled correctly")

    def test_invalid_config(self):
        with self.assertRaises(AttributeError):
            LexiconProvider(id="unittests", lexicon_config={})

    def test_config_resolver(self):
        # Given
        config_resolver = OnTheFlyLexiconConfigSource()

        # When
        config_resolver.set_ttl(666)

        # Then
        self.assertEqual(config_resolver.resolve("lexicon:ttl"), 666)
        self.assertEqual(config_resolver.resolve("lexicon:action"), "*")
        self.assertEqual(config_resolver.resolve("lexicon:type"), "*")
        self.assertEqual(config_resolver.resolve("lexicon:missing"), None)


class TestLexiconProviderApplyScenarios(TestCase):

    @mock.patch('lexicon.providers.gandi.Provider')
    def setUp(self, mock_provider):
        self.zone = Zone("blodapels.in.", [])
        self.provider = LexiconProvider(id="unittests",
                                        lexicon_config=lexicon_config)
        self.lexicon_records_one_octo_record = [
            {'type': 'A', 'name': 'test-many.blodapels.in', 'ttl': '1337',
             'content': '192.168.1.1', 'id': '747789'},
            {'type': 'A', 'name': 'test-many.blodapels.in', 'ttl': '1337',
             'content': '192.168.1.2', 'id': '747790'},
            {'type': 'A', 'name': 'test-many.blodapels.in', 'ttl': '1337',
             'content': '192.168.1.5', 'id': '747793'},
            {'type': 'A', 'name': 'test-many.blodapels.in', 'ttl': '1337',
             'content': '192.168.2.4', 'id': '747794'},
            {'type': 'A', 'name': 'test-many.blodapels.in', 'ttl': '1337',
             'content': '192.168.2.3', 'id': '747795'}]

        self.lexicon_records_non_unique_ids = [
            {'type': 'A', 'name': 'test-many.blodapels.in', 'ttl': '1337',
             'content': '192.168.1.1', 'id': 'test-many'},
            {'type': 'A', 'name': 'test-many.blodapels.in', 'ttl': '1337',
             'content': '192.168.1.2', 'id': 'test-many'},
            {'type': 'A', 'name': 'test-many.blodapels.in', 'ttl': '1337',
             'content': '192.168.1.5', 'id': 'test-many'},
            {'type': 'A', 'name': 'test-many.blodapels.in', 'ttl': '1337',
             'content': '192.168.2.4', 'id': 'test-many'},
            {'type': 'A', 'name': 'test-many.blodapels.in', 'ttl': '1337',
             'content': '192.168.2.3', 'id': 'test-many'}]

        self.octo_record = Record.new(Zone("blodapels.in.", []), 'test-many', {
            'type': 'A', 'ttl': 1337, 'values': ['192.168.1.1', '192.168.1.2',
                                                 '192.168.1.5', '192.168.2.4',
                                                 '192.168.2.3']})

        self.provider_mock = mock_provider.return_value

    def test_apply_create_delete(self):
        # Given
        changeset = [Create(r) for r in OCTODNS_DATA]

        record_to_del = Record.new(ZONE, 'unittest-del',
                                   {'ttl': 30, 'type': 'CNAME', 'value':
                                       'www.example.com.'},
                                   source=source)
        record_to_update = Record.new(ZONE, 'multi-value-record',
                                      {'ttl': 360, 'type': 'A', 'values':
                                          ['92.0.2.0', '192.0.2.1']},
                                      source=source)

        changeset.append(Delete(record_to_del))
        changeset.append(Update(record_to_update, record_to_update))

        plan = Plan(ZONE, ZONE, changeset, True)

        expected_create_calls = [
            mock.call(content='192.0.184.38',
                      rtype='A',
                      name='@.blodapels.in.'),
            mock.call(content='10 '
                              'spool.mail.example.com.',
                      rtype='MX',
                      name='@.blodapels.in.'),
            mock.call(content='50 fb.mail.example.com.',
                      rtype='MX',
                      name='@.blodapels.in.'),
            mock.call(content='v=spf1 include:_mailcus'
                              't.example.com ?all',
                      rtype='TXT',
                      name='@.blodapels.in.'),
            mock.call(content='0 0 0 .',
                      rtype='SRV',
                      name='_imap._tcp.blodapels.in.'),
            mock.call(content='0 1 993 mail.example.com.',
                      rtype='SRV',
                      name='_imaps._tcp.blodapels.in.'),
            mock.call(content='0 0 0 .',
                      rtype='SRV',
                      name='_pop3._tcp.blodapels.in.'),
            mock.call(content='10 1 995 '
                              'mail.example.com.',
                      rtype='SRV',
                      name='_pop3s._tcp.blodapels.in.'),
            mock.call(content='0 1 465 mail.example.com.',
                      rtype='SRV',
                      name='_submission.'
                           '_tcp.blodapels.in.'),
            mock.call(content='webmail.example.com.',
                      rtype='CNAME',
                      name='webmail.blodapels.in.'),
            mock.call(content='webredir.vip'
                              '.example.com.',
                      rtype='CNAME',
                      name='www.blodapels.in.'),
            mock.call(content='0 issue ";"',
                      rtype='CAA',
                      name='@.blodapels.in.'),
            mock.call(content='0 issuewild "letsencrypt.org"',
                      rtype='CAA',
                      name='@.blodapels.in.'),
        ]

        # When
        self.provider._apply(plan)

        # Then
        for exp in expected_create_calls:
            self.provider_mock.create_record.assert_has_calls([exp])

        self.assertEqual(len(self.provider_mock.create_record.call_args_list),
                         len(expected_create_calls),
                         "no extra calls to create_record recorded")

        self.provider_mock.delete_record.assert_called_once_with(
            identifier=None,
            content='www.example.com.',
            rtype='CNAME',
            name='unittest-del.blodapels.in.')
        self.provider_mock.update_record.assert_not_called()

    def test__apply_many_to_one(self):
        # Given
        self.provider.lexicon_client.provider.list_records.side_effect \
            = lambda *s: iter(self.lexicon_records_one_octo_record)

        octo_record = self.octo_record

        # When
        self.provider.populate(self.zone)

        # Then
        self.assertEqual(self.zone.records, {octo_record})
        self.assertEqual(
            self.provider.remembered_ids.get(octo_record, '192.168.1.1'),
            '747789')
        self.assertEqual(
            self.provider.remembered_ids.get(octo_record, '192.168.1.2'),
            '747790')
        self.assertEqual(
            self.provider.remembered_ids.get(octo_record, '192.168.1.5'),
            '747793')
        self.assertEqual(
            self.provider.remembered_ids.get(octo_record, '192.168.2.4'),
            '747794')
        self.assertEqual(
            self.provider.remembered_ids.get(octo_record, '192.168.2.3'),
            '747795')
        self.assertEqual(
            self.provider.remembered_ids.get(octo_record, 'not even valid ip'),
            None)
        self.assertEqual(
            self.provider.remembered_ids.get('', 'not even valid ip'), None)

        self.provider_mock.authenticate.assert_called_once_with()
        self.provider_mock.list_records. \
            assert_called_once_with(None, 'blodapels.in.', None)

    def test_apply_many_to_one_without_unique_ids(self):
        # Given
        self.provider.lexicon_client.provider.list_records.side_effect \
            = lambda *s: iter(self.lexicon_records_non_unique_ids)

        desired_zone = Zone("blodapels.in.", [])

        desired_record = Record.new(Zone("blodapels.in.", []), 'test-many', {
            'type': 'A', 'ttl': 1337, 'values': ['192.168.1.1', '192.168.1.2',
                                                 '192.168.1.3', '192.168.1.4',
                                                 '192.168.1.5', '192.168.7.7']}
                                    )
        desired_zone.add_record(desired_record)
        changes = {Update(existing=self.octo_record,
                          new=desired_record)}
        plan = Plan(desired=desired_zone,
                    existing=self.zone,
                    exists=True,
                    changes=changes)

        expected_caslls_for_create = [
            mock.call(content='192.168.1.3',
                      rtype='A',
                      name='test-many.blodapels.in.'),
            mock.call(content='192.168.1.4',
                      rtype='A',
                      name='test-many.blodapels.in.'),
            mock.call(content='192.168.7.7',
                      rtype='A',
                      name='test-many.blodapels.in.')]

        expected_calls_for_delete = [
            mock.call(content='192.168.2.3',
                      rtype='A',
                      name='test-many.blodapels.in.'),
            mock.call(content='192.168.2.4',
                      rtype='A',
                      name='test-many.blodapels.in.')]

        # When
        self.provider.populate(self.zone)
        self.provider.apply(plan)

        # Then
        self.provider_mock.update_record.assert_not_called()

        self.provider_mock.create_record.assert_has_calls(
            expected_caslls_for_create)

        self.provider_mock.delete_record.assert_has_calls(
            expected_calls_for_delete)

        self.assertEqual(self.provider_mock.delete_record.call_count, 2,
                         "Delete is called exactly twice")

    def test_apply_update_mix(self):
        # given
        self.provider.lexicon_client.provider.list_records.side_effect \
            = lambda *s: iter(self.lexicon_records_one_octo_record)

        desired_zone = Zone("blodapels.in.", [])

        desired_record = Record.new(Zone("blodapels.in.", []), 'test-many', {
            'type': 'A', 'ttl': 1337, 'values': ['192.168.1.1', '192.168.1.2',
                                                 '192.168.1.3', '192.168.1.4',
                                                 '192.168.1.5', '192.168.7.7']}
                                    )
        desired_zone.add_record(desired_record)

        changes = {Update(existing=self.octo_record,
                          new=desired_record)}

        plan = Plan(desired=desired_zone,
                    existing=self.zone,
                    exists=True,
                    changes=changes)

        expected_calls = [mock.call(identifier='747795',
                                    content='192.168.1.3',
                                    rtype='A',
                                    name='test-many.blodapels.in.'),
                          mock.call(identifier='747794',
                                    content='192.168.1.4',
                                    rtype='A',
                                    name='test-many.blodapels.in.')]

        # When
        self.provider.populate(self.zone)
        self.provider.apply(plan)

        # Then
        self.provider_mock.update_record.assert_has_calls(expected_calls)
        self.provider_mock.delete_record.assert_not_called()
        self.provider_mock.create_record.assert_called_once_with(
            content='192.168.7.7', rtype='A', name='test-many.blodapels.in.')
