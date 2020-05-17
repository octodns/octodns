#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

import logging
import shlex
from collections import defaultdict

from lexicon.client import Client as LexiconClient
from lexicon.config import ConfigResolver as LexiconConfigResolver, \
    ConfigSource as LexiconConfigSource
from .base import BaseProvider
from ..record import Record


class LexiconProvider(BaseProvider):
    """
    Wrapper to handle LexiconProviders in octodns

    lexicon:
        class: octodns.provider.lexicon.LexiconProvicer
        lexicon_config: lexicon config

    Configuration added to the lexicon_config block will be injected as a
    lexicon DictConfigSource. Further config sources read are the env config
    source.

    Example:

          gandi:
            class: octodns.provider.lexicon.LexiconProvider
            lexicon_config:
                provider_name: gandi
                domain: blodapels.in
                gandi:
                    auth_token: "better stored in environment variable"
                    api_protocol: rest

    """
    SUPPORTS = {'A', 'AAAA', 'CAA', 'CNAME', 'MX', 'NAPTR', 'NS', 'PTR',
                'SPF', 'SRV', 'TXT'}

    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False

    def __init__(self, id, lexicon_config, **kwargs):

        self.log = logging.getLogger('LexiconProvider[{}]'.format(id))
        super(LexiconProvider, self).__init__(id, **kwargs)

        self.log.info('__init__: id=%s, token=***, account=%s', id, kwargs)

        config = LexiconConfigResolver()
        self.dynamic_config = OnTheFlyLexiconConfigSource()

        config.with_config_source(self.dynamic_config) \
            .with_env().with_dict(lexicon_config)

        try:
            self.lexicon_client = LexiconClient(config)
        except AttributeError as e:
            self.log.error('Unable to parse config {!s}'.format(config))
            raise e

    def populate(self, zone, target=False, lenient=False):

        loaded_types = defaultdict(lambda: defaultdict(list))
        before = len(zone.records)

        exists = False

        self.lexicon_client.provider.authenticate()
        for lexicon_record in self.lexicon_client.provider.list_records(
                None, zone.name, None):
            # No way of knowing for sure whether a zone exists or not,
            # But if it has contents, it is safe to assume that it does.
            exists = True
            loaded_types[lexicon_record["id"]][lexicon_record["type"]] \
                .append(lexicon_record)

        for record_id, data_by_id in loaded_types.items():
            for record_type, lexicon_records in data_by_id.items():
                self.log.debug("Got {!s} from above".format(lexicon_records))

                _data_func = getattr(self, '_data_for_{}'.format(record_type))

                data = _data_func(record_type, lexicon_records)

                self.log.debug('populate: adding record {} records: {!s}'
                               .format(record_id, data))

                record = Record.new(zone, record_id, data, source=self)

                zone.add_record(record, lenient=lenient)

        self.log.info('populate:   found %s records, exists=%s',
                      len(zone.records) - before, before < len(zone.records))

        return exists

    def _apply(self, plan):
        """Required function of manager.py to actually apply a record change.

            :param plan: Contains the zones and changes to be made
            :type  plan: octodns.provider.base.Plan

            :type return: void
        """
        desired = plan.desired
        changes = plan.changes

        self.log.debug('_apply: zone=%s, len(changes)=%d', desired.name,
                       len(changes))

        self.lexicon_client.provider.authenticate()

        for change in changes:
            action = change.__class__.__name__
            _rrset_func = getattr(
                self, '_rrset_for_{}'.format(change.record._type))

            record_type = change.record._type
            contents = _rrset_func(change.record)
            identifier = change.record.fqdn
            name = change.record.fqdn

            self.dynamic_config.set_ttl(change.record.ttl)

            # a single record might have multiple values, but lexicon seems to
            # handle them one at a time, thus an A record with two rrsets will
            # have to be handled like two separate "actions"
            if action == 'Create':
                for content in contents:
                    self.lexicon_client.provider.create_record(
                        record_type, name, content)

            elif action == 'Update':

                # Some providers, such like the powerdns lexicon provider,
                # handle updates like so:
                #
                #         self._delete_record(identifier)
                #         return self._create_record(rtype, name, content)
                #
                # Therefore, for multiple additions to a particular record,
                # what seems to be the safest way, is to call update once, and
                # then do "create", because from what I can see in the
                # providers, create does not seem to delete old records.

                content_iterator = iter(contents)

                self.lexicon_client.provider \
                    .update_record(identifier, record_type,
                                   name, next(content_iterator))

                for content in content_iterator:
                    self.lexicon_client.provider \
                        .create_record(record_type, name, content)

            elif action == 'Delete':
                self.lexicon_client.provider \
                    .delete_record(identifier, record_type, name, None)

            else:
                raise RuntimeError(
                    "Unknown action {} for {!s}".format(action, change))

    def _data_for_multiple(self, type, lexicon_records):
        return {
            'ttl': lexicon_records[0]['ttl'],
            'type': type,
            'values': [r['content'] for r in lexicon_records]
        }

    def _data_for_MX(self, type, lexicon_records):
        values = []
        for record in lexicon_records:
            priority, exchange = shlex.split(record["content"])
            values.append({"priority": priority, "exchange": exchange})

        return {
            'ttl': lexicon_records[0]['ttl'],
            'type': type,
            'values': values
        }

    def _data_for_CNAME(self, type, lexicon_records):
        record = lexicon_records[0]
        return {
            'ttl': record['ttl'],
            'type': type,
            'value': record['content']
        }

    def _data_for_SRV(self, type, lexicon_records):
        values = []
        for record in lexicon_records:
            priority, weight, port, target = shlex.split(record['content'])

            values.append({
                'priority': priority,
                'weight': weight,
                'port': port,
                'target': target
            })
        return {
            'type': type,
            'ttl': lexicon_records[0]['ttl'],
            'values': values
        }

    _data_for_ALIAS = _data_for_CNAME

    _data_for_A = _data_for_multiple

    _data_for_TXT = _data_for_multiple

    def _rrset_for_multiple(self, octodns_record):
        return [content for content in octodns_record.values]

    def _rrset_for_MX(self, octodns_record):
        return ['{} {}'.format(c.preference, c.exchange)
                for c in octodns_record.values]

    def _rrset_for_CNAME(self, octodns_record):
        return [octodns_record.value]

    def _rrset_for_SRV(self, octodns_record):
        return ['{} {} {} {}'.format(
            c.priority, c.weight, c.port, c.target)
            for c in octodns_record.values]

    _rrset_for_ALIAS = _rrset_for_CNAME

    _rrset_for_A = _rrset_for_multiple

    _rrset_for_TXT = _rrset_for_multiple


class OnTheFlyLexiconConfigSource(LexiconConfigSource):

    def __init__(self, ttl=3600):
        super(OnTheFlyLexiconConfigSource, self).__init__()
        self.ttl = ttl

    def set_ttl(self, ttl):
        self.ttl = ttl

    def resolve(self, config_key):
        if config_key == "lexicon:ttl":
            return self.ttl
        # These two keys below are not used, because actions are handled in
        # _apply, The config needs to resolve, though, lest the config
        # validation will fail.
        elif config_key == 'lexicon:action':
            return '*'
        elif config_key == 'lexicon:type':
            return '*'
        else:
            return None
