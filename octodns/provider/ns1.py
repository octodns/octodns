#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger
from itertools import chain
from collections import OrderedDict, defaultdict
from ns1 import NS1
from ns1.rest.errors import RateLimitException, ResourceException
from pycountry_convert import country_alpha2_to_continent_code
from time import sleep
from uuid import uuid4

from six import text_type

from ..record import Record, Update
from .base import BaseProvider


class Ns1Exception(Exception):
    pass


class Ns1Client(object):
    log = getLogger('NS1Client')

    def __init__(self, api_key, retry_count=4):
        self.log.debug('__init__: retry_count=%d', retry_count)
        self.retry_count = retry_count

        client = NS1(apiKey=api_key)
        self._records = client.records()
        self._zones = client.zones()
        self._monitors = client.monitors()
        self._notifylists = client.notifylists()
        self._datasource = client.datasource()
        self._datafeed = client.datafeed()

        self._datasource_id = None
        self._feeds_for_monitors = None
        self._monitors_cache = None

    @property
    def datasource_id(self):
        if self._datasource_id is None:
            name = 'octoDNS NS1 Data Source'
            source = None
            for candidate in self.datasource_list():
                if candidate['name'] == name:
                    # Found it
                    source = candidate
                    break

            if source is None:
                self.log.info('datasource_id: creating datasource %s', name)
                # We need to create it
                source = self.datasource_create(name=name,
                                                sourcetype='nsone_monitoring')
                self.log.info('datasource_id:   id=%s', source['id'])

            self._datasource_id = source['id']

        return self._datasource_id

    @property
    def feeds_for_monitors(self):
        if self._feeds_for_monitors is None:
            self.log.debug('feeds_for_monitors: fetching & building')
            self._feeds_for_monitors = {
                f['config']['jobid']: f['id']
                for f in self.datafeed_list(self.datasource_id)
            }

        return self._feeds_for_monitors

    @property
    def monitors(self):
        if self._monitors_cache is None:
            self.log.debug('monitors: fetching & building')
            self._monitors_cache = \
                {m['id']: m for m in self.monitors_list()}
        return self._monitors_cache

    def datafeed_create(self, sourceid, name, config):
        ret = self._try(self._datafeed.create, sourceid, name, config)
        self.feeds_for_monitors[config['jobid']] = ret['id']
        return ret

    def datafeed_delete(self, sourceid, feedid):
        ret = self._try(self._datafeed.delete, sourceid, feedid)
        self._feeds_for_monitors = {
            k: v for k, v in self._feeds_for_monitors.items() if v != feedid
        }
        return ret

    def datafeed_list(self, sourceid):
        return self._try(self._datafeed.list, sourceid)

    def datasource_create(self, **body):
        return self._try(self._datasource.create, **body)

    def datasource_list(self):
        return self._try(self._datasource.list)

    def monitors_create(self, **params):
        body = {}
        ret = self._try(self._monitors.create, body, **params)
        self.monitors[ret['id']] = ret
        return ret

    def monitors_delete(self, jobid):
        ret = self._try(self._monitors.delete, jobid)
        self.monitors.pop(jobid)
        return ret

    def monitors_list(self):
        return self._try(self._monitors.list)

    def monitors_update(self, job_id, **params):
        body = {}
        ret = self._try(self._monitors.update, job_id, body, **params)
        self.monitors[ret['id']] = ret
        return ret

    def notifylists_delete(self, nlid):
        return self._try(self._notifylists.delete, nlid)

    def notifylists_create(self, **body):
        return self._try(self._notifylists.create, body)

    def notifylists_list(self):
        return self._try(self._notifylists.list)

    def records_create(self, zone, domain, _type, **params):
        return self._try(self._records.create, zone, domain, _type, **params)

    def records_delete(self, zone, domain, _type):
        return self._try(self._records.delete, zone, domain, _type)

    def records_retrieve(self, zone, domain, _type):
        return self._try(self._records.retrieve, zone, domain, _type)

    def records_update(self, zone, domain, _type, **params):
        return self._try(self._records.update, zone, domain, _type, **params)

    def zones_create(self, name):
        return self._try(self._zones.create, name)

    def zones_retrieve(self, name):
        return self._try(self._zones.retrieve, name)

    def _try(self, method, *args, **kwargs):
        tries = self.retry_count
        while True:  # We'll raise to break after our tries expire
            try:
                return method(*args, **kwargs)
            except RateLimitException as e:
                if tries <= 1:
                    raise
                period = float(e.period)
                self.log.warn('rate limit encountered, pausing '
                              'for %ds and trying again, %d remaining',
                              period, tries)
                sleep(period)
                tries -= 1


class Ns1Provider(BaseProvider):
    '''
    Ns1 provider

    ns1:
        class: octodns.provider.ns1.Ns1Provider
        api_key: env/NS1_API_KEY
    '''
    SUPPORTS_GEO = True
    SUPPORTS_DYNAMIC = True
    SUPPORTS = set(('A', 'AAAA', 'ALIAS', 'CAA', 'CNAME', 'MX', 'NAPTR',
                    'NS', 'PTR', 'SPF', 'SRV', 'TXT'))

    ZONE_NOT_FOUND_MESSAGE = 'server error: zone not found'

    _DYNAMIC_FILTERS = [{
        'config': {},
        'filter': 'up'
    }, {
        'config': {},
        'filter': u'geofence_regional'
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
    _CONTINENT_TO_REGIONS = {
        'AF': ('AFRICA',),
        'AS': ('ASIAPAC',),
        'EU': ('EUROPE',),
        'SA': ('SOUTH-AMERICA',),
        # TODO: what about CA, MX, and all the other NA countries?
        'NA': ('US-CENTRAL', 'US-EAST', 'US-WEST'),
    }

    def __init__(self, id, api_key, retry_count=4, *args, **kwargs):
        self.log = getLogger('Ns1Provider[{}]'.format(id))
        self.log.debug('__init__: id=%s, api_key=***, retry_count=%d', id,
                       retry_count)
        super(Ns1Provider, self).__init__(id, *args, **kwargs)

        self._client = Ns1Client(api_key, retry_count)

    def _encode_notes(self, data):
        return ' '.join(['{}:{}'.format(k, v)
                         for k, v in sorted(data.items())])

    def _parse_notes(self, note):
        data = {}
        if note:
            for piece in note.split(' '):
                try:
                    k, v = piece.split(':', 1)
                    data[k] = v
                except ValueError:
                    pass
        return data

    def _data_for_geo_A(self, _type, record):
        # record meta (which would include geo information is only
        # returned when getting a record's detail, not from zone detail
        geo = defaultdict(list)
        data = {
            'ttl': record['ttl'],
            'type': _type,
        }
        values, codes = [], []
        for answer in record.get('answers', []):
            meta = answer.get('meta', {})
            if meta:
                # country + state and country + province are allowed
                # in that case though, supplying a state/province would
                # be redundant since the country would supercede in when
                # resolving the record.  it is syntactically valid, however.
                country = meta.get('country', [])
                us_state = meta.get('us_state', [])
                ca_province = meta.get('ca_province', [])
                for cntry in country:
                    con = country_alpha2_to_continent_code(cntry)
                    key = '{}-{}'.format(con, cntry)
                    geo[key].extend(answer['answer'])
                for state in us_state:
                    key = 'NA-US-{}'.format(state)
                    geo[key].extend(answer['answer'])
                for province in ca_province:
                    key = 'NA-CA-{}'.format(province)
                    geo[key].extend(answer['answer'])
                for code in meta.get('iso_region_code', []):
                    key = code
                    geo[key].extend(answer['answer'])
            else:
                values.extend(answer['answer'])
                codes.append([])
        values = [text_type(x) for x in values]
        geo = OrderedDict(
            {text_type(k): [text_type(x) for x in v] for k, v in geo.items()}
        )
        data['values'] = values
        data['geo'] = geo
        return data

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
            # region (group name in the UI) is the pool name
            pool_name = answer['region']
            pool = pools[answer['region']]

            meta = answer['meta']
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
                if notes.get('from', False) == '--default--':
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
                pools[pool_name]['fallback'] = notes['fallback']

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

            rule = {
                'pool': pool_name,
                '_order': notes['rule-order'],
            }
            if geos:
                rule['geos'] = sorted(geos)
            rules.append(rule)

        # Order and convert to a list
        default = sorted(default)
        # Order
        rules.sort(key=lambda r: (r['_order'], r['pool']))

        return {
            'dynamic': {
                'pools': pools,
                'rules': rules,
            },
            'ttl': record['ttl'],
            'type': _type,
            'values': sorted(default),
        }

    def _data_for_A(self, _type, record):
        if record.get('tier', 1) > 1:
            # Advanced record, see if it's first answer has a note
            try:
                first_answer_note = record['answers'][0]['meta']['note']
            except (IndexError, KeyError):
                first_answer_note = ''
            # If that note includes a `from` (pool name) it's a dynamic record
            if 'from:' in first_answer_note:
                return self._data_for_dynamic_A(_type, record)
            # If not it's an old geo record
            return self._data_for_geo_A(_type, record)

        # This is a basic record, just convert it
        return {
            'ttl': record['ttl'],
            'type': _type,
            'values': [text_type(x) for x in record['short_answers']]
        }

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
            ns1_zone_name = zone.name[:-1]
            ns1_zone = self._client.zones_retrieve(ns1_zone_name)

            records = []
            geo_records = []

            # change answers for certain types to always be absolute
            for record in ns1_zone['records']:
                if record['type'] in ['ALIAS', 'CNAME', 'MX', 'NS', 'PTR',
                                      'SRV']:
                    for i, a in enumerate(record['short_answers']):
                        if not a.endswith('.'):
                            record['short_answers'][i] = '{}.'.format(a)

                if record.get('tier', 1) > 1:
                    # Need to get the full record data for geo records
                    record = self._client.records_retrieve(ns1_zone_name,
                                                           record['domain'],
                                                           record['type'])
                    geo_records.append(record)
                else:
                    records.append(record)

            exists = True
        except ResourceException as e:
            if e.message != self.ZONE_NOT_FOUND_MESSAGE:
                raise
            records = []
            geo_records = []
            exists = False

        before = len(zone.records)
        # geo information isn't returned from the main endpoint, so we need
        # to query for all records with geo information
        zone_hash = {}
        for record in chain(records, geo_records):
            _type = record['type']
            if _type not in self.SUPPORTS:
                continue
            data_for = getattr(self, '_data_for_{}'.format(_type))
            name = zone.hostname_from_fqdn(record['domain'])
            data = data_for(_type, record)
            record = Record.new(zone, name, data, source=self, lenient=lenient)
            zone_hash[(_type, name)] = record
        [zone.add_record(r, lenient=lenient) for r in zone_hash.values()]
        self.log.info('populate:   found %s records, exists=%s',
                      len(zone.records) - before, exists)
        return exists

    def _params_for_geo_A(self, record):
        # purposefully set non-geo answers to have an empty meta,
        # so that we know we did this on purpose if/when troubleshooting
        params = {
            'answers': [{"answer": [x], "meta": {}} for x in record.values],
            'ttl': record.ttl,
        }

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

        return params, None

    def _monitors_for(self, record):
        monitors = {}

        if getattr(record, 'dynamic', False):
            expected_host = record.fqdn[:-1]
            expected_type = record._type

            for monitor in self._client.monitors.values():
                data = self._parse_notes(monitor['notes'])
                if expected_host == data['host'] and \
                   expected_type == data['type']:
                    # This monitor does not belong to this record
                    config = monitor['config']
                    value = config['host']
                    monitors[value] = monitor

        return monitors

    def _uuid(self):
        return uuid4().hex

    def _feed_create(self, monitor):
        monitor_id = monitor['id']
        self.log.debug('_feed_create: monitor=%s', monitor_id)
        # TODO: looks like length limit is 64 char
        name = '{} - {}'.format(monitor['name'], self._uuid()[:6])

        # Create the data feed
        config = {
            'jobid': monitor_id,
        }
        feed = self._client.datafeed_create(self._client.datasource_id, name,
                                            config)
        feed_id = feed['id']
        self.log.debug('_feed_create:   feed=%s', feed_id)

        return feed_id

    def _monitor_create(self, monitor):
        self.log.debug('_monitor_create: monitor="%s"', monitor['name'])
        # Create the notify list
        notify_list = [{
            'config': {
                'sourceid': self._client.datasource_id,
            },
            'type': 'datafeed',
        }]
        nl = self._client.notifylists_create(name=monitor['name'],
                                             notify_list=notify_list)
        nl_id = nl['id']
        self.log.debug('_monitor_create:   notify_list=%s', nl_id)

        # Create the monitor
        monitor['notify_list'] = nl_id
        monitor = self._client.monitors_create(**monitor)
        monitor_id = monitor['id']
        self.log.debug('_monitor_create:   monitor=%s', monitor_id)

        return monitor_id, self._feed_create(monitor)

    def _monitor_gen(self, record, value):
        host = record.fqdn[:-1]
        _type = record._type

        request = r'GET {path} HTTP/1.0\r\nHost: {host}\r\n' \
            r'User-agent: NS1\r\n\r\n'.format(path=record.healthcheck_path,
                                              host=record.healthcheck_host)

        return {
            'active': True,
            'config': {
                'connect_timeout': 2000,
                'host': value,
                'port': record.healthcheck_port,
                'response_timeout': 10000,
                'send': request,
                'ssl': record.healthcheck_protocol == 'HTTPS',
            },
            'frequency': 60,
            'job_type': 'tcp',
            'name': '{} - {} - {}'.format(host, _type, value),
            'notes': self._encode_notes({
                'host': host,
                'type': _type,
            }),
            'policy': 'quorum',
            'rapid_recheck': False,
            'region_scope': 'fixed',
            # TODO: what should we do here dal, sjc, lga, sin, ams
            'regions': ['lga'],
            'rules': [{
                'comparison': 'contains',
                'key': 'output',
                'value': '200 OK',
            }],
        }

    def _monitor_is_match(self, expected, have):
        # Make sure what we have matches what's in expected exactly. Anything
        # else in have will be ignored.
        for k, v in expected.items():
            if have.get(k, '--missing--') != v:
                return False

        return True

    def _monitor_sync(self, record, value, existing):
        self.log.debug('_monitor_sync: record=%s, value=%s', record.fqdn,
                       value)
        expected = self._monitor_gen(record, value)

        if existing:
            self.log.debug('_monitor_sync:   existing=%s', existing['id'])
            monitor_id = existing['id']

            if not self._monitor_is_match(expected, existing):
                self.log.debug('_monitor_sync:   existing needs update')
                # Update the monitor to match expected, everything else will be
                # left alone and assumed correct
                self._client.monitors_update(monitor_id, **expected)

            feed_id = self._client.feeds_for_monitors.get(monitor_id)
            if feed_id is None:
                self.log.warn('_monitor_sync: %s (%s) missing feed, creating',
                              existing['name'], monitor_id)
                feed_id = self._feed_create(existing)
        else:
            self.log.debug('_monitor_sync:   needs create')
            # We don't have an existing monitor create it (and related bits)
            monitor_id, feed_id = self._monitor_create(expected)

        return monitor_id, feed_id

    def _monitors_gc(self, record, active_monitor_ids=None):
        self.log.debug('_monitors_gc: record=%s, active_monitor_ids=%s',
                       record.fqdn, active_monitor_ids)

        if active_monitor_ids is None:
            active_monitor_ids = set()

        for monitor in self._monitors_for(record).values():
            monitor_id = monitor['id']
            if monitor_id in active_monitor_ids:
                continue

            self.log.debug('_monitors_gc:   deleting %s', monitor_id)

            feed_id = self._client.feeds_for_monitors.get(monitor_id)
            if feed_id:
                self._client.datafeed_delete(self._client.datasource_id,
                                             feed_id)

            self._client.monitors_delete(monitor_id)

            notify_list_id = monitor['notify_list']
            self._client.notifylists_delete(notify_list_id)

    def _params_for_dynamic_A(self, record):
        pools = record.dynamic.pools

        # Convert rules to regions
        regions = {}
        for i, rule in enumerate(record.dynamic.rules):
            pool_name = rule.data['pool']

            notes = {
                'rule-order': i,
            }

            fallback = pools[pool_name].data.get('fallback', None)
            if fallback:
                notes['fallback'] = fallback

            country = set()
            georegion = set()
            us_state = set()

            for geo in rule.data.get('geos', []):
                n = len(geo)
                if n == 8:
                    # US state, e.g. NA-US-KY
                    us_state.add(geo[-2:])
                elif n == 5:
                    # Country, e.g. EU-FR
                    country.add(geo[-2:])
                else:
                    # Continent, e.g. AS
                    georegion.update(self._CONTINENT_TO_REGIONS[geo])

            meta = {
                'note': self._encode_notes(notes),
            }
            if georegion:
                meta['georegion'] = sorted(georegion)
            if country:
                meta['country'] = sorted(country)
            if us_state:
                meta['us_state'] = sorted(us_state)

            regions[pool_name] = {
                'meta': meta,
            }

        existing_monitors = self._monitors_for(record)
        active_monitors = set()

        # Build a list of primary values for each pool, including their
        # feed_id (monitor)
        pool_answers = defaultdict(list)
        for pool_name, pool in sorted(pools.items()):
            for value in pool.data['values']:
                weight = value['weight']
                value = value['value']
                existing = existing_monitors.get(value)
                monitor_id, feed_id = self._monitor_sync(record, value,
                                                         existing)
                active_monitors.add(monitor_id)
                pool_answers[pool_name].append({
                    'answer': [value],
                    'weight': weight,
                    'feed_id': feed_id,
                })

        default_answers = [{
            'answer': [v],
            'weight': 1,
        } for v in record.values]

        # Build our list of answers
        answers = []
        for pool_name in sorted(pools.keys()):
            priority = 1

            # Dynamic/health checked
            current_pool_name = pool_name
            seen = set()
            while current_pool_name and current_pool_name not in seen:
                seen.add(current_pool_name)
                pool = pools[current_pool_name]
                for answer in pool_answers[current_pool_name]:
                    answer = {
                        'answer': answer['answer'],
                        'meta': {
                            'priority': priority,
                            'note': self._encode_notes({
                                'from': current_pool_name,
                            }),
                            'up': {
                                'feed': answer['feed_id'],
                            },
                            'weight': answer['weight'],
                        },
                        'region': pool_name,  # the one we're answering
                    }
                    answers.append(answer)

                current_pool_name = pool.data.get('fallback', None)
                priority += 1

            # Static/default
            for answer in default_answers:
                answer = {
                    'answer': answer['answer'],
                    'meta': {
                        'priority': priority,
                        'note': self._encode_notes({
                            'from': '--default--',
                        }),
                        'up': True,
                        'weight': 1,
                    },
                    'region': pool_name,  # the one we're answering
                }
                answers.append(answer)

        return {
            'answers': answers,
            'filters': self._DYNAMIC_FILTERS,
            'regions': regions,
            'ttl': record.ttl,
        }, active_monitors

    def _params_for_A(self, record):
        if getattr(record, 'dynamic', False):
            return self._params_for_dynamic_A(record)
        elif hasattr(record, 'geo'):
            return self._params_for_geo_A(record)

        return {
            'answers': record.values,
            'ttl': record.ttl,
        }, None

    _params_for_AAAA = _params_for_A
    _params_for_NS = _params_for_A

    def _params_for_SPF(self, record):
        # NS1 seems to be the only provider that doesn't want things
        # escaped in values so we have to strip them here and add
        # them when going the other way
        values = [v.replace('\\;', ';') for v in record.values]
        return {'answers': values, 'ttl': record.ttl}, None

    _params_for_TXT = _params_for_SPF

    def _params_for_CAA(self, record):
        values = [(v.flags, v.tag, v.value) for v in record.values]
        return {'answers': values, 'ttl': record.ttl}, None

    # TODO: dynamic CNAME support
    def _params_for_CNAME(self, record):
        return {'answers': [record.value], 'ttl': record.ttl}, None

    _params_for_ALIAS = _params_for_CNAME
    _params_for_PTR = _params_for_CNAME

    def _params_for_MX(self, record):
        values = [(v.preference, v.exchange) for v in record.values]
        return {'answers': values, 'ttl': record.ttl}, None

    def _params_for_NAPTR(self, record):
        values = [(v.order, v.preference, v.flags, v.service, v.regexp,
                   v.replacement) for v in record.values]
        return {'answers': values, 'ttl': record.ttl}, None

    def _params_for_SRV(self, record):
        values = [(v.priority, v.weight, v.port, v.target)
                  for v in record.values]
        return {'answers': values, 'ttl': record.ttl}, None

    def _extra_changes(self, desired, changes, **kwargs):
        self.log.debug('_extra_changes: desired=%s', desired.name)

        changed = set([c.record for c in changes])

        extra = []
        for record in desired.records:
            if record in changed or not getattr(record, 'dynamic', False):
                # Already changed, or no dynamic , no need to check it
                continue

            for have in self._monitors_for(record).values():
                value = have['config']['host']
                expected = self._monitor_gen(record, value)
                # TODO: find values which have missing monitors
                if not self._monitor_is_match(expected, have):
                    self.log.info('_extra_changes: monitor mis-match for %s',
                                  expected['name'])
                    extra.append(Update(record, record))
                    break
                if not have.get('notify_list'):
                    self.log.info('_extra_changes: broken monitor no notify '
                                  'list %s (%s)', have['name'], have['id'])
                    extra.append(Update(record, record))
                    break

        return extra

    def _apply_Create(self, ns1_zone, change):
        new = change.new
        zone = new.zone.name[:-1]
        domain = new.fqdn[:-1]
        _type = new._type
        params, active_monitor_ids = \
            getattr(self, '_params_for_{}'.format(_type))(new)
        self._client.records_create(zone, domain, _type, **params)
        self._monitors_gc(new, active_monitor_ids)

    def _apply_Update(self, ns1_zone, change):
        new = change.new
        zone = new.zone.name[:-1]
        domain = new.fqdn[:-1]
        _type = new._type
        params, active_monitor_ids = \
            getattr(self, '_params_for_{}'.format(_type))(new)
        self._client.records_update(zone, domain, _type, **params)
        self._monitors_gc(new, active_monitor_ids)

    def _apply_Delete(self, ns1_zone, change):
        existing = change.existing
        zone = existing.zone.name[:-1]
        domain = existing.fqdn[:-1]
        _type = existing._type
        self._client.records_delete(zone, domain, _type)
        self._monitors_gc(existing)

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        self.log.debug('_apply: zone=%s, len(changes)=%d', desired.name,
                       len(changes))

        domain_name = desired.name[:-1]
        try:
            ns1_zone = self._client.zones_retrieve(domain_name)
        except ResourceException as e:
            if e.message != self.ZONE_NOT_FOUND_MESSAGE:
                raise
            self.log.debug('_apply:   no matching zone, creating')
            ns1_zone = self._client.zones_create(domain_name)

        for change in changes:
            class_name = change.__class__.__name__
            getattr(self, '_apply_{}'.format(class_name))(ns1_zone,
                                                          change)
