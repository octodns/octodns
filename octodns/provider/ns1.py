#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from pprint import pprint

from logging import getLogger
from itertools import chain
from collections import defaultdict
from ns1 import NS1
from ns1.rest.errors import RateLimitException, ResourceException
from pycountry_convert import country_alpha2_to_continent_code
from re import compile as re_compile
from time import sleep

from six import text_type

from ..record import Record
from .base import BaseProvider


class Ns1Exception(Exception):
    pass


class Ns1Provider(BaseProvider):
    '''
    Ns1 provider

    nsone:
        class: octodns.provider.ns1.Ns1Provider
        api_key: env/NS1_API_KEY
    '''
    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = True
    SUPPORTS = set(('A', 'AAAA', 'ALIAS', 'CAA', 'CNAME', 'MX', 'NAPTR',
                    'NS', 'PTR', 'SPF', 'SRV', 'TXT'))

    ZONE_NOT_FOUND_MESSAGE = 'server error: zone not found'

    _FALLBACK_RE = re_compile(r'fallback:(?P<fallback>[\w\-_]+)')
    _DYNAMIC_FILTERS = [{
        'config': {},
        'filter': 'up'
    }, {
        'config': {},
        'filter': u'geotarget_regional'
    }, {
        'config': {},
        'filter': u'select_first_region'
    }, {
        'config': {
            'eliminate': u'1'
        },
        'filter': 'priority'
    }, {
        'config': {},
        'filter': u'weighted_shuffle'
    }, {
        'config': {
            'N': u'1'
        },
        'filter': u'select_first_n'
    }]
    _REGION_TO_CONTINENT = {
        'AFRICA': 'AF',
        'ASIAPAC': 'AS',
        'EUROPE': 'EU',
        'SOUTH-AMERICA': 'SA',
        'US-CENTRAL': 'NA',
        'US-EAST': 'NA',
        'US-WEST': 'NA',
    }
    _CONTINENT_TO_REGION = {
        'AF': ('AFRICA',),
        'AS': ('ASIAPAC',),
        'EU': ('EUROPE',),
        'SA': ('SOUTH-AMERICA',),
        # TODO: what about CA, MX, and all the other NA countries?
        'NA': ('US-CENTRAL', 'US-EAST', 'US-WEST'),
    }

    def __init__(self, id, api_key, *args, **kwargs):
        self.log = getLogger('Ns1Provider[{}]'.format(id))
        self.log.debug('__init__: id=%s, api_key=***', id)
        super(Ns1Provider, self).__init__(id, *args, **kwargs)
        self._client = NS1(apiKey=api_key)

    def _data_for_geo(self, _type, record):
        raise Exception('boom')

    def _parse_notes(self, note):
        notes = {}

        for p in note.split(' '):
            try:
                k, v = p.split(':', 1)
            except ValueError:
                # Failed to parse, just ignore
                continue
            if v == 'true':
                v = True
            elif v == 'false':
                v = False
            notes[k] = v

        return notes

    def _data_for_dynamic_A(self, _type, record):
        # First make sure we have the expected filters config
        if self._DYNAMIC_FILTERS != record['filters']:
            self.log.error('_data_for_dynamic_A: %s %s has unsupported '
                           'filters', record['domain'], _type)
            raise Ns1Exception('Unrecognized advanced record')

        # All regions (pools) will include the list of default values
        # (eventually) at higher priorities, we'll just add them to this set to
        # we'll have the complete collection.
        default = set()
        # Fill out the pools by walking the answers and looking at their
        # region.
        pools = defaultdict(lambda: {'fallback': None, 'values': []})
        for answer in record['answers']:
            meta = answer['meta']
            # region (group name in the UI) is the pool name
            pool = pools[answer['region']]
            value = text_type(answer['answer'][0])
            if meta['priority'] == 1:
                # priority 1 means this answer is part of the pools own values
                pool['values'].append({
                    'value': value,
                    'weight': int(meta.get('weight', 1)),
                })
            else:
                # It's a fallback, we only care about it if it's a
                # final/default
                notes = self._parse_notes(meta.get('note', ''))
                if notes.get('default', False):
                    default.add(value)

        # The regions objects map to rules, but it's a bit fuzzy since they're
        # tied to pools on the NS1 side, e.g. we can only have 1 rule per pool,
        # that may eventually run into problems, but I don't have any use-cases
        # examples currently where it would
        rules = []
        for pool_name, region in sorted(record['regions'].items()):
            meta = region['meta']
            notes = self._parse_notes(meta.get('note', ''))

            # The group notes field in the UI is a `note` on the region here,
            # that's where we can find our pool's fallback.
            if 'fallback' in notes:
                # set the fallback pool name
                pools[pool_name]['falback'] = notes['fallback']

            geos = set()

            # continents are mapped (imperfectly) to regions, but what about
            # Canada/North America
            for georegion in meta.get('georegion', []):
                geos.add(self._REGION_TO_CONTINENT[georegion])

            # Countries are easy enough to map, we just have ot find their
            # continent
            for country in meta.get('country', []):
                con = country_alpha2_to_continent_code(country)
                geos.add('{}-{}'.format(con, country))

            # States are easy too, just assume NA-US (CA providences aren't
            # supported by octoDNS currently)
            for state in meta.get('us_state', []):
                geos.add('NA-US-{}'.format(state))

            rules.append({
                'geos': sorted(geos),
                'pool': pool_name,
                '_order': notes['rule-order'],
            })

        # Order and convert to a list
        default = sorted(default)
        # Order
        rules.sort(key=lambda r: (r['_order'], r['pool']))

        return {
            'dynamic': {
                'pools': pools,
                'rules': rules,
            },
            'values': sorted(default),
        }

    def _data_for_A(self, _type, record):
        data = {
            'ttl': record['ttl'],
            'type': _type,
        }
        if 'answers' in record:
            # This is a dynamic record
            data.update(self._data_for_dynamic_A(_type, record))
            pprint(data)
        else:
            # This is a simple record
            values = [text_type(x) for x in record['short_answers']]
            data['values'] = values

        pprint(data)

        return data

    _data_for_AAAA = _data_for_A

    def _data_for_SPF(self, _type, record):
        values = [v.replace(';', '\\;') for v in record['short_answers']]
        return {
            'ttl': record['ttl'],
            'type': _type,
            'values': values
        }

    _data_for_TXT = _data_for_SPF

    def _data_for_CAA(self, _type, record):
        values = []
        for answer in record['short_answers']:
            flags, tag, value = answer.split(' ', 2)
            values.append({
                'flags': flags,
                'tag': tag,
                'value': value,
            })
        return {
            'ttl': record['ttl'],
            'type': _type,
            'values': values,
        }

    def _data_for_CNAME(self, _type, record):
        try:
            value = record['short_answers'][0]
        except IndexError:
            value = None
        return {
            'ttl': record['ttl'],
            'type': _type,
            'value': value,
        }

    _data_for_ALIAS = _data_for_CNAME
    _data_for_PTR = _data_for_CNAME

    def _data_for_MX(self, _type, record):
        values = []
        for answer in record['short_answers']:
            preference, exchange = answer.split(' ', 1)
            values.append({
                'preference': preference,
                'exchange': exchange,
            })
        return {
            'ttl': record['ttl'],
            'type': _type,
            'values': values,
        }

    def _data_for_NAPTR(self, _type, record):
        values = []
        for answer in record['short_answers']:
            order, preference, flags, service, regexp, replacement = \
                answer.split(' ', 5)
            values.append({
                'flags': flags,
                'order': order,
                'preference': preference,
                'regexp': regexp,
                'replacement': replacement,
                'service': service,
            })
        return {
            'ttl': record['ttl'],
            'type': _type,
            'values': values,
        }

    def _data_for_NS(self, _type, record):
        return {
            'ttl': record['ttl'],
            'type': _type,
            'values': [a if a.endswith('.') else '{}.'.format(a)
                       for a in record['short_answers']],
        }

    def _data_for_SRV(self, _type, record):
        values = []
        for answer in record['short_answers']:
            priority, weight, port, target = answer.split(' ', 3)
            values.append({
                'priority': priority,
                'weight': weight,
                'port': port,
                'target': target,
            })
        return {
            'ttl': record['ttl'],
            'type': _type,
            'values': values,
        }

    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s, target=%s, lenient=%s',
                       zone.name,
                       target, lenient)

        try:
            nsone_zone_name = zone.name[:-1]
            nsone_zone = self._client.loadZone(nsone_zone_name)

            records = []

            # change answers for certain types to always be absolute
            for record in nsone_zone.data['records']:
                if record['tier'] > 1:
                    # This is an advanced record so we need to load its full
                    # details
                    full = self._client.loadRecord(record['domain'],
                                                   record['type'])
                    records.append(full.data)
                else:
                    # This is a simple record, the data in the zone is enough
                    records.append(record)

            if False and record['type'] in ['ALIAS', 'CNAME', 'MX', 'NS',
                                            'PTR', 'SRV']:
                for i, a in enumerate(record['short_answers']):
                    if not a.endswith('.'):
                        record['short_answers'][i] = '{}.'.format(a)

            exists = True
        except ResourceException as e:
            if e.message != self.ZONE_NOT_FOUND_MESSAGE:
                raise
            records = []
            exists = False

        pprint({
            'records': records,
        })

        before = len(zone.records)
        # geo information isn't returned from the main endpoint, so we need
        # to query for all records with geo information
        zone_hash = {}
        for record in chain(records):
            _type = record['type']
            if _type not in self.SUPPORTS:
                continue
            data_for = getattr(self, '_data_for_{}'.format(_type))
            name = zone.hostname_from_fqdn(record['domain'])
            pprint([record, _type, data_for(_type, record)])
            record = Record.new(zone, name, data_for(_type, record),
                                source=self, lenient=lenient)
            zone_hash[(_type, name)] = record
        [zone.add_record(r, lenient=lenient) for r in zone_hash.values()]
        self.log.info('populate:   found %s records, exists=%s',
                      len(zone.records) - before, exists)
        return exists

    def _params_for_A(self, record):
        params = {'answers': record.values, 'ttl': record.ttl}
        if hasattr(record, 'geo'):
            # purposefully set non-geo answers to have an empty meta,
            # so that we know we did this on purpose if/when troubleshooting
            params['answers'] = [{"answer": [x], "meta": {}}
                                 for x in record.values]
            has_country = False
            for iso_region, target in record.geo.items():
                key = 'iso_region_code'
                value = iso_region
                if not has_country and \
                   len(value.split('-')) > 1:  # pragma: nocover
                    has_country = True
                for answer in target.values:
                    params['answers'].append(
                        {
                            'answer': [answer],
                            'meta': {key: [value]},
                        },
                    )
            params['filters'] = []
            if has_country:
                params['filters'].append(
                    {"filter": "shuffle", "config": {}}
                )
                params['filters'].append(
                    {"filter": "geotarget_country", "config": {}}
                )
                params['filters'].append(
                    {"filter": "select_first_n",
                     "config": {"N": 1}}
                )
        self.log.debug("params for A: %s", params)
        return params

    _params_for_AAAA = _params_for_A
    _params_for_NS = _params_for_A

    def _params_for_SPF(self, record):
        # NS1 seems to be the only provider that doesn't want things
        # escaped in values so we have to strip them here and add
        # them when going the other way
        values = [v.replace('\\;', ';') for v in record.values]
        return {'answers': values, 'ttl': record.ttl}

    _params_for_TXT = _params_for_SPF

    def _params_for_CAA(self, record):
        values = [(v.flags, v.tag, v.value) for v in record.values]
        return {'answers': values, 'ttl': record.ttl}

    def _params_for_CNAME(self, record):
        return {'answers': [record.value], 'ttl': record.ttl}

    _params_for_ALIAS = _params_for_CNAME
    _params_for_PTR = _params_for_CNAME

    def _params_for_MX(self, record):
        values = [(v.preference, v.exchange) for v in record.values]
        return {'answers': values, 'ttl': record.ttl}

    def _params_for_NAPTR(self, record):
        values = [(v.order, v.preference, v.flags, v.service, v.regexp,
                   v.replacement) for v in record.values]
        return {'answers': values, 'ttl': record.ttl}

    def _params_for_SRV(self, record):
        values = [(v.priority, v.weight, v.port, v.target)
                  for v in record.values]
        return {'answers': values, 'ttl': record.ttl}

    def _get_name(self, record):
        return record.fqdn[:-1] if record.name == '' else record.name

    def _apply_Create(self, nsone_zone, change):
        new = change.new
        name = self._get_name(new)
        _type = new._type
        params = getattr(self, '_params_for_{}'.format(_type))(new)
        meth = getattr(nsone_zone, 'add_{}'.format(_type))
        try:
            meth(name, **params)
        except RateLimitException as e:
            period = float(e.period)
            self.log.warn('_apply_Create: rate limit encountered, pausing '
                          'for %ds and trying again', period)
            sleep(period)
            meth(name, **params)

    def _apply_Update(self, nsone_zone, change):
        existing = change.existing
        name = self._get_name(existing)
        _type = existing._type
        record = nsone_zone.loadRecord(name, _type)
        new = change.new
        params = getattr(self, '_params_for_{}'.format(_type))(new)
        try:
            record.update(**params)
        except RateLimitException as e:
            period = float(e.period)
            self.log.warn('_apply_Update: rate limit encountered, pausing '
                          'for %ds and trying again', period)
            sleep(period)
            record.update(**params)

    def _apply_Delete(self, nsone_zone, change):
        existing = change.existing
        name = self._get_name(existing)
        _type = existing._type
        record = nsone_zone.loadRecord(name, _type)
        try:
            record.delete()
        except RateLimitException as e:
            period = float(e.period)
            self.log.warn('_apply_Delete: rate limit encountered, pausing '
                          'for %ds and trying again', period)
            sleep(period)
            record.delete()

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        self.log.debug('_apply: zone=%s, len(changes)=%d', desired.name,
                       len(changes))

        domain_name = desired.name[:-1]
        try:
            nsone_zone = self._client.loadZone(domain_name)
        except ResourceException as e:
            if e.message != self.ZONE_NOT_FOUND_MESSAGE:
                raise
            self.log.debug('_apply:   no matching zone, creating')
            nsone_zone = self._client.createZone(domain_name)

        for change in changes:
            class_name = change.__class__.__name__
            getattr(self, '_apply_{}'.format(class_name))(nsone_zone,
                                                          change)
