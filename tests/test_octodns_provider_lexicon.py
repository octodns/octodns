from unittest import TestCase

import mock
from mock import Mock

from octodns.provider.lexicon import LexiconProvider, \
    OnTheFlyLexiconConfigSource
from octodns.provider.plan import Plan
from octodns.record import Record, Change, Create, Delete, Update
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
     'id': '_submission._tcp'}
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
]


class TestLexiconProvider(TestCase):
    lexicon_config = {
        "provider_name": "gandi",
        "domain": 'blodapels.in',
        "gandi": {
            "api_protocol": "rest",
            "auth_token": "X"
        }
    }

    @mock.patch('lexicon.providers.gandi.Provider')
    def test_populate(self, mock_provider):
        # Given
        provider = LexiconProvider(id="unittests",
                                   lexicon_config=self.lexicon_config)
        zone = Zone("blodapels.in.", [])

        provider.lexicon_client.provider.list_records.side_effect \
            = lambda *s: iter(LEXICON_DATA)

        # When
        provider.populate(zone=zone)

        # Then
        self.assertEqual(zone.records, set(OCTODNS_DATA))
        self.assertTrue(mock_provider.called, "authenticate was called")

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

    @mock.patch('lexicon.providers.gandi.Provider')
    def test__apply(self, mock_provider):
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

        provider = LexiconProvider(id="unittests",
                                   lexicon_config=self.lexicon_config)

        # When
        provider._apply(plan)

        # Then
        pass

    @mock.patch('lexicon.providers.gandi.Provider')
    def test_apply_weird_stuff(self, _):
        # Given
        provider = LexiconProvider(id="unittests",
                                   lexicon_config=self.lexicon_config)

        with self.assertRaises(RuntimeError):
            provider._apply(BadPlan())


class CrashChange(Change):

    def __init__(self, new):
        super(CrashChange, self).__init__(None, new)


class BadPlan:
    desired = Mock()
    changes = [CrashChange(OCTODNS_DATA[0])]
