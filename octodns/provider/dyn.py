#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from collections import defaultdict
from dyn.tm.errors import DynectGetError
from dyn.tm.services.dsf import DSFARecord, DSFAAAARecord, DSFCNAMERecord, \
    DSFFailoverChain, DSFMonitor, DSFNode, DSFRecordSet, DSFResponsePool, \
    DSFRuleset, TrafficDirector, get_all_dsf_monitors, get_all_dsf_services, \
    get_response_pool
from dyn.tm.session import DynectSession
from dyn.tm.zones import Zone as DynZone
from logging import getLogger
from threading import Lock
from uuid import uuid4

from ..record import Record, Update
from ..record.geo import GeoCodes
from .base import BaseProvider


###############################################################################
#
# The following monkey patching is to work around functionality that is lacking
# from DSFMonitor. You cannot set host or path (which we need) and there's no
# update method. What's more host & path aren't publically accessible on the
# object so you can't see their current values and depending on how the object
# came to be (constructor vs pulled from the api) the "private" location of
# those fields varies :-(
#
###############################################################################
def _monitor_host_get(self):
    return self._host or self._options['host']


DSFMonitor.host = property(_monitor_host_get)


def _monitor_host_set(self, value):
    if self._options is None:
        self._options = {}
    self._host = self._options['host'] = value


DSFMonitor.host = DSFMonitor.host.setter(_monitor_host_set)


def _monitor_path_get(self):
    return self._path or self._options['path']


DSFMonitor.path = property(_monitor_path_get)


def _monitor_path_set(self, value):
    if self._options is None:
        self._options = {}
    self._path = self._options['path'] = value


DSFMonitor.path = DSFMonitor.path.setter(_monitor_path_set)


def _monitor_protocol_get(self):
    return self._protocol


DSFMonitor.protocol = property(_monitor_protocol_get)


def _monitor_protocol_set(self, value):
    self._protocol = value


DSFMonitor.protocol = DSFMonitor.protocol.setter(_monitor_protocol_set)


def _monitor_port_get(self):
    return self._port or self._options['port']


DSFMonitor.port = property(_monitor_port_get)


def _monitor_port_set(self, value):
    if self._options is None:
        self._options = {}
    self._port = self._options['port'] = value


DSFMonitor.port = DSFMonitor.port.setter(_monitor_port_set)


def _monitor_update(self, host, path, protocol, port):
    # I can't see how to actually do this with the client lib so
    # I'm having to hack around it. Have to provide all the
    # options or else things complain
    return self._update({
        'protocol': protocol,
        'options': {
            'host': host,
            'path': path,
            'port': port,
            'timeout': DynProvider.MONITOR_TIMEOUT,
            'header': DynProvider.MONITOR_HEADER,
        }
    })


DSFMonitor.update = _monitor_update
###############################################################################


def _monitor_doesnt_match(monitor, host, path, protocol, port):
    return monitor.host != host or monitor.path != path or \
        monitor.protocol != protocol or int(monitor.port) != port


class _CachingDynZone(DynZone):
    log = getLogger('_CachingDynZone')

    _cache = {}

    @classmethod
    def get(cls, zone_name, create=False):
        cls.log.debug('get: zone_name=%s, create=%s', zone_name, create)
        # This works in dyn zone names, without the trailing .
        try:
            dyn_zone = cls._cache[zone_name]
            cls.log.debug('get:   cache hit')
        except KeyError:
            cls.log.debug('get:   cache miss')
            try:
                dyn_zone = _CachingDynZone(zone_name)
                cls.log.debug('get:   fetched')
            except DynectGetError:
                if not create:
                    cls.log.debug("get:   doesn't exist")
                    return None
                # this value shouldn't really matter, it's not tied to
                # whois or anything
                hostname = 'hostmaster@{}'.format(zone_name[:-1])
                # Try again with the params necessary to create
                dyn_zone = _CachingDynZone(zone_name, ttl=3600,
                                           contact=hostname,
                                           serial_style='increment')
                cls.log.debug('get:   created')
            cls._cache[zone_name] = dyn_zone

        return dyn_zone

    @classmethod
    def flush_zone(cls, zone_name):
        '''Flushes the zone cache, if there is one'''
        cls.log.debug('flush_zone: zone_name=%s', zone_name)
        try:
            del cls._cache[zone_name]
        except KeyError:
            pass

    def __init__(self, zone_name, *args, **kwargs):
        super(_CachingDynZone, self).__init__(zone_name, *args, **kwargs)
        self.flush_cache()

    def flush_cache(self):
        self._cached_records = None

    def get_all_records(self):
        if self._cached_records is None:
            self._cached_records = \
                super(_CachingDynZone, self).get_all_records()
        return self._cached_records

    def publish(self):
        super(_CachingDynZone, self).publish()
        self.flush_cache()


def _dynamic_value_sort_key(value):
    return value['value']


class DynProvider(BaseProvider):
    '''
    Dynect Managed DNS provider

    dyn:
        class: octodns.provider.dyn.DynProvider
        # Your dynect customer name (required)
        customer: cust
        # Your dynect username (required)
        username: user
        # Your dynect password (required)
        password: pass
        # Whether or not to support TrafficDirectors and enable GeoDNS
        # (optional, default is false)
        traffic_directors_enabled: true

    Note: due to the way dyn.tm.session.DynectSession is managing things we can
    only really have a single DynProvider configured. When you create a
    DynectSession it's stored in a thread-local singleton. You don't invoke
    methods on this session or a client that holds on to it. The client
    libraries grab their per-thread session by accessing the singleton through
    DynectSession.get_session(). That fundamentally doesn't support having more
    than one account active at a time. See DynProvider._check_dyn_sess for some
    related bits.
    '''

    RECORDS_TO_TYPE = {
        'a_records': 'A',
        'aaaa_records': 'AAAA',
        'alias_records': 'ALIAS',
        'caa_records': 'CAA',
        'cname_records': 'CNAME',
        'mx_records': 'MX',
        'naptr_records': 'NAPTR',
        'ns_records': 'NS',
        'ptr_records': 'PTR',
        'sshfp_records': 'SSHFP',
        'spf_records': 'SPF',
        'srv_records': 'SRV',
        'txt_records': 'TXT',
    }
    TYPE_TO_RECORDS = {v: k for k, v in RECORDS_TO_TYPE.items()}
    SUPPORTS = set(TYPE_TO_RECORDS.keys())
    SUPPORTS_ROOT_NS = False

    # https://help.dyn.com/predefined-geotm-regions-groups/
    REGION_CODES = {
        'NA': 11,  # Continental North America
        'SA': 12,  # Continental South America
        'EU': 13,  # Continental Europe
        'AF': 14,  # Continental Africa
        'AS': 15,  # Continental Asia
        'OC': 16,  # Continental Australia/Oceania
        'AN': 17,  # Continental Antarctica
    }
    # Reverse of ^
    REGION_CODES_LOOKUP = {code: geo for geo, code in REGION_CODES.items()}

    MONITOR_HEADER = 'User-Agent: Dyn Monitor'
    MONITOR_TIMEOUT = 10

    _sess_create_lock = Lock()

    def __init__(self, id, customer, username, password,
                 traffic_directors_enabled=False, *args, **kwargs):
        self.log = getLogger('DynProvider[{}]'.format(id))
        self.log.debug('__init__: id=%s, customer=%s, username=%s, '
                       'password=***, traffic_directors_enabled=%s', id,
                       customer, username, traffic_directors_enabled)
        # we have to set this before calling super b/c SUPPORTS_GEO requires it
        self.traffic_directors_enabled = traffic_directors_enabled
        super(DynProvider, self).__init__(id, *args, **kwargs)
        self.customer = customer
        self.username = username
        self.password = password

        self._cache = {}
        self._traffic_directors = None
        self._traffic_director_monitors = None

    @property
    def SUPPORTS_GEO(self):
        return self.traffic_directors_enabled

    @property
    def SUPPORTS_DYNAMIC(self):
        return self.traffic_directors_enabled

    def _check_dyn_sess(self):
        # We don't have to worry about locking for the check since the
        # underlying pieces are pre-thread. We can check to see if this thread
        # has a session and if so we're good to go.
        if DynectSession.get_session() is None:
            # We need to create a new session for this thread and DynectSession
            # creation is not thread-safe so we have to do the locking. If we
            # don't and multiple sessions start creation before the the first
            # has finished (long time b/c it makes http calls) the subsequent
            # creates will blow away DynectSession._instances, potentially
            # multiple times if there are multiple creates in flight. Only the
            # last of these initial concurrent creates will exist in
            # DynectSession._instances dict and the others will be lost. When
            # this thread later tries to make api calls there won't be an
            # accessible session available for it to use.
            with self._sess_create_lock:
                DynectSession(self.customer, self.username, self.password)

    def _data_for_A(self, _type, records):
        return {
            'type': _type,
            'ttl': records[0].ttl,
            'values': [r.address for r in records]
        }

    _data_for_AAAA = _data_for_A

    def _data_for_ALIAS(self, _type, records):
        # See note on ttl in _kwargs_for_ALIAS
        record = records[0]
        return {
            'type': _type,
            'ttl': record.ttl,
            'value': record.alias
        }

    def _data_for_CAA(self, _type, records):
        return {
            'type': _type,
            'ttl': records[0].ttl,
            'values': [{'flags': r.flags, 'tag': r.tag, 'value': r.value}
                       for r in records],
        }

    def _data_for_CNAME(self, _type, records):
        record = records[0]
        return {
            'type': _type,
            'ttl': record.ttl,
            'value': record.cname,
        }

    def _data_for_MX(self, _type, records):
        return {
            'type': _type,
            'ttl': records[0].ttl,
            'values': [{'preference': r.preference, 'exchange': r.exchange}
                       for r in records],
        }

    def _data_for_NAPTR(self, _type, records):
        return {
            'type': _type,
            'ttl': records[0].ttl,
            'values': [{
                'order': r.order,
                'preference': r.preference,
                'flags': r.flags,
                'service': r.services,
                'regexp': r.regexp,
                'replacement': r.replacement,
            } for r in records]
        }

    def _data_for_NS(self, _type, records):
        return {
            'type': _type,
            'ttl': records[0].ttl,
            'values': [r.nsdname for r in records]
        }

    def _data_for_PTR(self, _type, records):
        record = records[0]
        return {
            'type': _type,
            'ttl': record.ttl,
            'value': record.ptrdname,
        }

    def _data_for_SPF(self, _type, records):
        record = records[0]
        return {
            'type': _type,
            'ttl': record.ttl,
            'values': [r.txtdata for r in records]
        }

    _data_for_TXT = _data_for_SPF

    def _data_for_SSHFP(self, _type, records):
        return {
            'type': _type,
            'ttl': records[0].ttl,
            'values': [{
                'algorithm': r.algorithm,
                'fingerprint_type': r.fptype,
                'fingerprint': r.fingerprint,
            } for r in records],
        }

    def _data_for_SRV(self, _type, records):
        return {
            'type': _type,
            'ttl': records[0].ttl,
            'values': [{
                'priority': r.priority,
                'weight': r.weight,
                'port': r.port,
                'target': r.target,
            } for r in records],
        }

    @property
    def traffic_directors(self):
        if self._traffic_directors is None:
            self._check_dyn_sess()

            tds = defaultdict(dict)
            for td in get_all_dsf_services():
                try:
                    fqdn, _type = td.label.split(':', 1)
                except ValueError:
                    self.log.warn("Unsupported TrafficDirector '%s'", td.label)
                    continue
                tds[fqdn][_type] = td
            self._traffic_directors = dict(tds)

        return self._traffic_directors

    def _populate_geo_traffic_director(self, zone, fqdn, _type, td, rulesets,
                                       lenient):
        # We start out with something that will always show change in case this
        # is a busted TD. This will prevent us from creating a duplicate td.
        # We'll overwrite this with real data provided we have it
        geo = {}
        data = {
            'geo': geo,
            'type': _type,
            'ttl': td.ttl,
            'values': ['0.0.0.0']
        }
        for ruleset in rulesets:
            try:
                record_set = ruleset.response_pools[0].rs_chains[0] \
                    .record_sets[0]
            except IndexError:
                # problems indicate a malformed ruleset, ignore it
                continue
            if ruleset.label.startswith('default:'):
                data_for = getattr(self, '_data_for_{}'.format(_type))
                data.update(data_for(_type, record_set.records))
            else:
                # We've stored the geo in label
                try:
                    code, _ = ruleset.label.split(':', 1)
                except ValueError:
                    continue
                values = [r.address for r in record_set.records]
                geo[code] = values

        name = zone.hostname_from_fqdn(fqdn)
        record = Record.new(zone, name, data, source=self)
        zone.add_record(record, lenient=lenient)

        return record

    def _value_for_address(self, _type, record):
        return {
            'value': record.address,
            'weight': record.weight,
        }

    _value_for_A = _value_for_address
    _value_for_AAAA = _value_for_address

    def _value_for_CNAME(self, _type, record):
        return {
            'value': record.cname,
            'weight': record.weight,
        }

    def _populate_dynamic_pools(self, _type, rulesets, response_pools):
        default = {}
        pools = {}

        data_for = getattr(self, '_data_for_{}'.format(_type))
        value_for = getattr(self, '_value_for_{}'.format(_type))

        # Build the list of pools, we can't just read them off of rules b/c we
        # won't see unused pools there. If/when we dis-allow unused pools we
        # could probably change that and avoid the refresh
        for response_pool in response_pools:
            # We have to refresh the response pool to have access to its
            # rs_chains and thus records, yeah... :-(
            # TODO: look at rulesets first b/c they won't need a refresh...
            response_pool.refresh()
            try:
                record_set = response_pool.rs_chains[0] \
                    .record_sets[0]
            except IndexError:
                # problems indicate a malformed ruleset, ignore it
                self.log.warn('_populate_dynamic_pools: '
                              'malformed response_pool "%s" ignoring',
                              response_pool.label)
                continue

            label = response_pool.label

            if label == 'default':
                # The default pool has the base record values
                default = data_for(_type, record_set.records)
            else:
                if label not in pools:
                    # First time we've seen it get its data
                    # Note we'll have to set fallbacks as we go through rules
                    # b/c we can't determine them here
                    values = [value_for(_type, r) for r in record_set.records]
                    # Sort to ensure consistent ordering so we can compare them
                    values.sort(key=_dynamic_value_sort_key)
                    pools[label] = {
                        'values': values,
                    }

        return default, pools

    def _populate_dynamic_rules(self, rulesets, pools):
        rules = []

        # Build the list of rules based on the rulesets
        for ruleset in rulesets:
            if ruleset.label.startswith('default:'):
                # Ignore the default, it's implicit in our model
                continue

            num_pools = len(ruleset.response_pools)
            if num_pools > 0:
                # Find the primary pool for this rule
                pool = ruleset.response_pools[0].label
                # TODO: verify pool exists
                if num_pools > 1:
                    # We have a fallback, record it in the approrpriate pool.
                    # Note we didn't have fallback info when we populated the
                    # pools above so we're filling that info in here. It's
                    # possible that rules will have disagreeing values for the
                    # fallbacks. That's annoying but a sync should fix it and
                    # match stuff up with the config.
                    fallback = ruleset.response_pools[1].label
                    # TODO: verify fallback exists
                    if fallback != 'default':
                        pools[pool]['fallback'] = fallback
            else:
                self.log.warn('_populate_dynamic_pools: '
                              'ruleset "%s" has no response_pools',
                              ruleset.label)
                continue

            # OK we have the rule's pool info, record it and work on the rule's
            # matching criteria
            rule = {
                'pool': pool,
            }

            criteria_type = ruleset.criteria_type
            if criteria_type == 'geoip':
                # Geo
                geo = ruleset.criteria['geoip']
                geos = []
                # Dyn uses the same 2-letter codes as octoDNS (except for
                # continents) but it doesn't have the hierary, e.g. US is
                # just US, not NA-US. We'll have to map these things back
                for code in geo['country']:
                    geos.append(GeoCodes.country_to_code(code))
                for code in geo['province']:
                    geos.append(GeoCodes.province_to_code(code.upper()))
                for code in geo['region']:
                    geos.append(self.REGION_CODES_LOOKUP[int(code)])
                geos.sort()
                rule['geos'] = geos
            elif criteria_type == 'always':
                pass
            else:
                self.log.warn('_populate_dynamic_rules: '
                              'unsupported criteria_type "%s", ignoring',
                              criteria_type)
                continue

            rules.append(rule)

        return rules

    def _populate_dynamic_traffic_director(self, zone, fqdn, _type, td,
                                           rulesets, lenient):
        # We'll go ahead and grab pools too, using all will include unref'd
        # pools
        response_pools = td.all_response_pools

        # Populate pools
        default, pools = self._populate_dynamic_pools(_type, rulesets,
                                                      response_pools)

        # Populate rules
        rules = self._populate_dynamic_rules(rulesets, pools)

        # We start out with something that will always show
        # change in case this is a busted TD. This will prevent us from
        # creating a duplicate td. We'll overwrite this with real data
        # provide we have it
        data = {
            'dynamic': {
                'pools': pools,
                'rules': rules,
            },
            'type': _type,
            'ttl': td.ttl,
        }
        # Include default's information in data
        data.update(default)

        name = zone.hostname_from_fqdn(fqdn)
        record = Record.new(zone, name, data, source=self, lenient=lenient)
        zone.add_record(record, lenient=lenient)

        return record

    def _is_traffic_director_dyanmic(self, td, rulesets):
        for ruleset in rulesets:
            try:
                pieces = ruleset.label.split(':')
                if len(pieces) == 2:
                    # It matches octoDNS's format
                    int(pieces[0])
                    # It's an integer, so probably rule_num, thus dynamic
                    return True
            except (IndexError, ValueError):
                pass
        # We didn't see any rulesets that look like a dynamic record so maybe
        # geo...
        return False

    def _populate_traffic_directors(self, zone, lenient):
        self.log.debug('_populate_traffic_directors: zone=%s, lenient=%s',
                       zone.name, lenient)
        td_records = set()
        for fqdn, types in self.traffic_directors.items():
            for _type, td in types.items():
                # Does this TD belong to the current zone
                td_zone = '{}.'.format(td.nodes[0]['zone'])
                if td_zone != zone.name:
                    # Doesn't belong to the current zone, skip it
                    continue
                # critical to call rulesets once, each call loads them :-(
                rulesets = td.rulesets
                if self._is_traffic_director_dyanmic(td, rulesets):
                    record = \
                        self._populate_dynamic_traffic_director(zone, fqdn,
                                                                _type, td,
                                                                rulesets,
                                                                lenient)
                else:
                    record = \
                        self._populate_geo_traffic_director(zone, fqdn, _type,
                                                            td, rulesets,
                                                            lenient)
                td_records.add(record)

        return td_records

    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s, target=%s, lenient=%s', zone.name,
                       target, lenient)

        exists = False
        before = len(zone.records)

        self._check_dyn_sess()

        td_records = set()
        if self.traffic_directors_enabled:
            td_records = self._populate_traffic_directors(zone, lenient)
            exists = True

        dyn_zone = _CachingDynZone.get(zone.name[:-1])

        if dyn_zone:
            exists = True
            values = defaultdict(lambda: defaultdict(list))
            for _type, records in dyn_zone.get_all_records().items():
                if _type == 'soa_records':
                    continue
                _type = self.RECORDS_TO_TYPE[_type]
                for record in records:
                    record_name = zone.hostname_from_fqdn(record.fqdn)
                    values[record_name][_type].append(record)

            for name, types in values.items():
                for _type, records in types.items():
                    data_for = getattr(self, '_data_for_{}'.format(_type))
                    data = data_for(_type, records)
                    record = Record.new(zone, name, data, source=self,
                                        lenient=lenient)
                    if record not in td_records:
                        zone.add_record(record, lenient=lenient)

        self.log.info('populate:   found %s records, exists=%s',
                      len(zone.records) - before, exists)
        return exists

    def _extra_changes(self, desired, changes, **kwargs):
        self.log.debug('_extra_changes: desired=%s', desired.name)

        changed = set([c.record for c in changes])

        extra = []
        for record in desired.records:
            if record in changed or not getattr(record, 'geo', False):
                # Already changed, or no geo, no need to check it
                continue
            label = '{}:{}'.format(record.fqdn, record._type)
            try:
                monitor = self.traffic_director_monitors[label]
            except KeyError:
                self.log.info('_extra_changes: health-check missing for %s',
                              label)
                extra.append(Update(record, record))
                continue
            if _monitor_doesnt_match(monitor, record.healthcheck_host,
                                     record.healthcheck_path,
                                     record.healthcheck_protocol,
                                     record.healthcheck_port):
                self.log.info('_extra_changes: health-check mis-match for %s',
                              label)
                extra.append(Update(record, record))

        return extra

    def _kwargs_for_A(self, record):
        return [{
            'address': v,
            'ttl': record.ttl,
        } for v in record.values]

    _kwargs_for_AAAA = _kwargs_for_A

    def _kwargs_for_CAA(self, record):
        return [{
            'flags': v.flags,
            'tag': v.tag,
            'ttl': record.ttl,
            'value': v.value,
        } for v in record.values]

    def _kwargs_for_CNAME(self, record):
        return [{
            'cname': record.value,
            'ttl': record.ttl,
        }]

    def _kwargs_for_ALIAS(self, record):
        # NOTE: Dyn's UI doesn't allow editing of ALIAS ttl, but the API seems
        # to accept and store the values we send it just fine. No clue if they
        # do anything with them. I'd assume they just obey the TTL of the
        # record that we're pointed at which makes sense.
        return [{
            'alias': record.value,
            'ttl': record.ttl,
        }]

    def _kwargs_for_MX(self, record):
        return [{
            'preference': v.preference,
            'exchange': v.exchange,
            'ttl': record.ttl,
        } for v in record.values]

    def _kwargs_for_NAPTR(self, record):
        return [{
            'flags': v.flags,
            'order': v.order,
            'preference': v.preference,
            'regexp': v.regexp,
            'replacement': v.replacement,
            'services': v.service,
            'ttl': record.ttl,
        } for v in record.values]

    def _kwargs_for_NS(self, record):
        return [{
            'nsdname': v,
            'ttl': record.ttl,
        } for v in record.values]

    def _kwargs_for_PTR(self, record):
        return [{
            'ptrdname': record.value,
            'ttl': record.ttl,
        }]

    def _kwargs_for_SSHFP(self, record):
        return [{
            'algorithm': v.algorithm,
            'fptype': v.fingerprint_type,
            'fingerprint': v.fingerprint,
        } for v in record.values]

    def _kwargs_for_SPF(self, record):
        return [{
            'txtdata': v,
            'ttl': record.ttl,
        } for v in record.chunked_values]

    def _kwargs_for_SRV(self, record):
        return [{
            'port': v.port,
            'priority': v.priority,
            'target': v.target,
            'weight': v.weight,
            'ttl': record.ttl,
        } for v in record.values]

    _kwargs_for_TXT = _kwargs_for_SPF

    @property
    def traffic_director_monitors(self):
        if self._traffic_director_monitors is None:
            self.log.debug('traffic_director_monitors: loading')
            self._traffic_director_monitors = \
                {m.label: m for m in get_all_dsf_monitors()}

        return self._traffic_director_monitors

    def _traffic_director_monitor(self, record):
        fqdn = record.fqdn
        label = '{}:{}'.format(fqdn, record._type)
        try:
            try:
                monitor = self.traffic_director_monitors[label]
                self.log.debug('_traffic_director_monitor: existing for %s',
                               label)
            except KeyError:
                # UNTIL 1.0 We don't have one for the new label format, see if
                # we still have one for the old and update it
                monitor = self.traffic_director_monitors[fqdn]
                self.log.info('_traffic_director_monitor: upgrading label '
                              'to %s', label)
                monitor.label = label
                self.traffic_director_monitors[label] = \
                    self.traffic_director_monitors[fqdn]
                del self.traffic_director_monitors[fqdn]
            if _monitor_doesnt_match(monitor, record.healthcheck_host,
                                     record.healthcheck_path,
                                     record.healthcheck_protocol,
                                     record.healthcheck_port):
                self.log.info('_traffic_director_monitor: updating monitor '
                              'for %s', label)
                monitor.update(record.healthcheck_host,
                               record.healthcheck_path,
                               record.healthcheck_protocol,
                               record.healthcheck_port)
            return monitor
        except KeyError:
            self.log.info('_traffic_director_monitor: creating monitor '
                          'for %s', label)
            monitor = DSFMonitor(label, protocol=record.healthcheck_protocol,
                                 response_count=2, probe_interval=60,
                                 retries=2, port=record.healthcheck_port,
                                 active='Y', host=record.healthcheck_host,
                                 timeout=self.MONITOR_TIMEOUT,
                                 header=self.MONITOR_HEADER,
                                 path=record.healthcheck_path)
            self._traffic_director_monitors[label] = monitor
            return monitor

    def _find_or_create_geo_pool(self, td, pools, label, _type, values,
                                 monitor_id=None):
        for pool in pools:
            if pool.label != label:
                continue
            records = pool.rs_chains[0].record_sets[0].records
            record_values = sorted([r.address for r in records])
            if record_values == values:
                # it's a match
                return pool
        # we need to create the pool
        _class = {
            'A': DSFARecord,
            'AAAA': DSFAAAARecord
        }[_type]
        records = [_class(v) for v in values]
        record_set = DSFRecordSet(_type, label, serve_count=len(records),
                                  records=records, dsf_monitor_id=monitor_id)
        chain = DSFFailoverChain(label, record_sets=[record_set])
        pool = DSFResponsePool(label, rs_chains=[chain])
        pool.create(td)

        # We need to store the newly created pool in the pools list since the
        # caller won't know if it was newly created or not. This will allow us
        # to find this pool again if another rule references it and avoid
        # creating duplicates
        pools.append(pool)

        return pool

    def _dynamic_records_for_A(self, values, record_extras):
        return [DSFARecord(v['value'], weight=v.get('weight', 1),
                           **record_extras)
                for v in values]

    def _dynamic_records_for_AAAA(self, values, record_extras):
        return [DSFAAAARecord(v['value'], weight=v.get('weight', 1),
                              **record_extras)
                for v in values]

    def _dynamic_records_for_CNAME(self, values, record_extras):
        return [DSFCNAMERecord(v['value'], weight=v.get('weight', 1),
                               **record_extras)
                for v in values]

    def _find_or_create_dynamic_pool(self, td, pools, label, _type, values,
                                     monitor_id=None, record_extras={}):

        # Sort the values for consistent ordering so that we can compare
        values = sorted(values, key=_dynamic_value_sort_key)
        # Ensure that weight is included and if not use the default
        values = [{
            'value': v['value'],
            'weight': v.get('weight', 1),
        } for v in values]

        # Walk through our existing pools looking for a match we can use
        for pool in pools:
            # It must have the same label
            if pool.label != label:
                continue
            try:
                records = pool.rs_chains[0].record_sets[0].records
            except IndexError:
                # No values, can't match
                continue
            # And the (sorted) values must match once converted for comparison
            # purposes
            value_for = getattr(self, '_value_for_{}'.format(_type))
            record_values = [value_for(_type, r) for r in records]
            if record_values == values:
                # it's a match
                return pool

        # We don't have this pool and thus need to create it
        records_for = getattr(self, '_dynamic_records_for_{}'.format(_type))
        records = records_for(values, record_extras)
        record_set = DSFRecordSet(_type, label, serve_count=1, records=records,
                                  dsf_monitor_id=monitor_id)
        chain = DSFFailoverChain(label, record_sets=[record_set])
        pool = DSFResponsePool(label, rs_chains=[chain])
        pool.create(td)

        # We need to store the newly created pool in the pools list since the
        # caller won't know if it was newly created or not. This will allow us
        # to find this pool again if another rule references it and avoid
        # creating duplicates
        pools.append(pool)

        return pool

    def _mod_geo_rulesets(self, td, change):
        new = change.new

        # Response Pools
        pools = {}

        # Get existing pools. This should be simple, but it's not b/c the dyn
        # api is a POS. We need all response pools so we can GC and check to
        # make sure that what we're after doesn't already exist.
        # td.all_response_pools just returns thin objects that don't include
        # their rs_chains (and children down to actual records.) We could just
        # foreach over those turning them into full DSFResponsePool objects
        # with get_response_pool, but that'd be N round-trips. We can avoid
        # those round trips in cases where the pools are in use in rules where
        # they're already full objects.

        # First up populate all the full pools we have under rules, the _
        # prevents a td.refresh we don't need :-( seriously?
        existing_rulesets = td._rulesets
        for ruleset in existing_rulesets:
            for pool in ruleset.response_pools:
                pools[pool.response_pool_id] = pool
        # Reverse sort the existing_rulesets by _ordering so that we'll remove
        # them in that order later, this will ensure that we remove the old
        # default before any of the old geo rules preventing it from catching
        # everything.
        existing_rulesets.sort(key=lambda r: r._ordering, reverse=True)

        # Now we need to find any pools that aren't referenced by rules
        for pool in td.all_response_pools:
            rpid = pool.response_pool_id
            if rpid not in pools:
                # we want this one, but it's thin, inflate it
                pools[rpid] = get_response_pool(rpid, td)
        # now that we have full objects for the complete set of existing pools,
        # a list will be more useful
        pools = pools.values()

        # Rulesets

        # We need to make sure and insert the new rules after any existing
        # rules so they won't take effect before we've had a chance to add
        # response pools to them. I've tried both publish=False (which is
        # completely broken in the client) and creating the rulesets with
        # response_pool_ids neither of which appear to work from the client
        # library. If there are no existing rulesets fallback to 0
        insert_at = max([
            int(r._ordering)
            for r in existing_rulesets
        ] + [-1]) + 1
        self.log.debug('_mod_geo_rulesets: insert_at=%d', insert_at)

        # add the default
        label = 'default:{}'.format(uuid4().hex)
        ruleset = DSFRuleset(label, 'always', [])
        ruleset.create(td, index=insert_at)
        pool = self._find_or_create_geo_pool(td, pools, 'default', new._type,
                                             new.values)
        # There's no way in the client lib to create a ruleset with an existing
        # pool (ref'd by id) so we have to do this round-a-bout.
        active_pools = {
            'default': pool.response_pool_id
        }
        ruleset.add_response_pool(pool.response_pool_id)

        monitor_id = self._traffic_director_monitor(new).dsf_monitor_id
        # Geos ordered least to most specific so that parents will always be
        # created before their children (and thus can be referenced
        geos = sorted(new.geo.items(), key=lambda d: d[0])
        for _, geo in geos:
            if geo.subdivision_code:
                criteria = {
                    'province': geo.subdivision_code.lower()
                }
            elif geo.country_code:
                criteria = {
                    'country': geo.country_code
                }
            else:
                criteria = {
                    'region': self.REGION_CODES[geo.continent_code]
                }

            label = '{}:{}'.format(geo.code, uuid4().hex)
            ruleset = DSFRuleset(label, 'geoip', [], {
                'geoip': criteria
            })
            # Something you have to call create others the constructor does it
            ruleset.create(td, index=insert_at)

            first = geo.values[0]
            pool = self._find_or_create_geo_pool(td, pools, first, new._type,
                                                 geo.values, monitor_id)
            active_pools[geo.code] = pool.response_pool_id
            ruleset.add_response_pool(pool.response_pool_id)

            # look for parent rulesets we can add in the chain
            for code in geo.parents:
                try:
                    pool_id = active_pools[code]
                    # looking at client lib code, index > exists appends
                    ruleset.add_response_pool(pool_id, index=999)
                except KeyError:
                    pass
            # and always add default as the last
            pool_id = active_pools['default']
            ruleset.add_response_pool(pool_id, index=999)

        # we're done with active_pools as a lookup, convert it in to a set of
        # the ids in use
        active_pools = set(active_pools.values())
        # Clean up unused response_pools
        for pool in pools:
            if pool.response_pool_id in active_pools:
                continue
            pool.delete()

        # Clean out the old rulesets
        for ruleset in existing_rulesets:
            ruleset.delete()

    def _mod_geo_Create(self, dyn_zone, change):
        new = change.new
        fqdn = new.fqdn
        _type = new._type
        label = '{}:{}'.format(fqdn, _type)
        node = DSFNode(new.zone.name, fqdn)
        td = TrafficDirector(label, ttl=new.ttl, nodes=[node], publish='Y')
        self.log.debug('_mod_geo_Create: td=%s', td.service_id)
        self._mod_geo_rulesets(td, change)
        self.traffic_directors[fqdn] = {
            _type: td
        }

    def _mod_geo_Update(self, dyn_zone, change):
        new = change.new
        if not new.geo:
            # New record doesn't have geo we're going from a TD to a regular
            # record
            self._mod_Create(dyn_zone, change)
            self._mod_geo_Delete(dyn_zone, change)
            return
        try:
            td = self.traffic_directors[new.fqdn][new._type]
        except KeyError:
            # There's no td, this is actually a create, we must be going from a
            # non-geo to geo record so delete the regular record as well
            self._mod_geo_Create(dyn_zone, change)
            self._mod_Delete(dyn_zone, change)
            return
        self._mod_geo_rulesets(td, change)

    def _mod_geo_Delete(self, dyn_zone, change):
        existing = change.existing
        fqdn_tds = self.traffic_directors[existing.fqdn]
        _type = existing._type
        fqdn_tds[_type].delete()
        del fqdn_tds[_type]

    def _mod_dynamic_rulesets(self, td, change):
        new = change.new

        # TODO: make sure we can update TTLs
        if td.ttl != new.ttl:
            td.ttl = new.ttl

        # Get existing pools. This should be simple, but it's not b/c the dyn
        # api is a POS. We need all response pools so we can GC and check to
        # make sure that what we're after doesn't already exist.
        # td.all_response_pools just returns thin objects that don't include
        # their rs_chains (and children down to actual records.) We could just
        # foreach over those turning them into full DSFResponsePool objects
        # with get_response_pool, but that'd be N round-trips. We can avoid
        # those round trips in cases where the pools are in use in rules where
        # they're already full objects.

        # First up populate all the pools we have under rules, the _ prevents a
        # td.refresh we don't need :-( seriously?
        existing_rulesets = td._rulesets
        pools = {}
        for ruleset in existing_rulesets:
            for pool in ruleset.response_pools:
                pools[pool.response_pool_id] = pool

        # Reverse sort the existing_rulesets by _ordering so that we'll remove
        # them in that order later, this will ensure that we remove the old
        # default before any of the old geo rules preventing it from catching
        # everything.
        existing_rulesets.sort(key=lambda r: r._ordering, reverse=True)

        # Add in any pools that aren't currently referenced by rules
        for pool in td.all_response_pools:
            rpid = pool.response_pool_id
            if rpid not in pools:
                # we want this one, but it's thin, inflate it
                pools[rpid] = get_response_pool(rpid, td)
        # now that we have full objects for the complete set of existing pools,
        # a list will be more useful
        pools = list(pools.values())

        # Rulesets

        # We need to make sure and insert the new rules after any existing
        # rules so they won't take effect before we've had a chance to add
        # response pools to them. I've tried both publish=False (which is
        # completely broken in the client) and creating the rulesets with
        # response_pool_ids neither of which appear to work from the client
        # library. If there are no existing rulesets fallback to 0
        insert_at = max([
            int(r._ordering)
            for r in existing_rulesets
        ] + [-1]) + 1
        self.log.debug('_mod_dynamic_rulesets: insert_at=%d', insert_at)

        # Add the base record values as the ultimate/unhealthchecked default
        label = 'default:{}'.format(uuid4().hex)
        ruleset = DSFRuleset(label, 'always', [])
        ruleset.create(td, index=insert_at)
        # If/when we go beyond A, AAAA, and CNAME this will have to get
        # more intelligent, probably a weighted_values method on Record objects
        # or something like that?
        try:
            values = new.values
        except AttributeError:
            values = [new.value]
        values = [{
            'value': v,
            'weight': 1,
        } for v in values]
        # For these defaults we need to set them to always be served and to
        # ignore any health checking (since they won't have one)
        pool = self._find_or_create_dynamic_pool(td, pools, 'default',
                                                 new._type, values,
                                                 record_extras={
                                                     'automation': 'manual',
                                                     'eligible': True,
                                                 })
        # There's no way in the client lib to create a ruleset with an existing
        # pool (ref'd by id) so we have to do this round-a-bout.
        active_pools = {
            # TODO: disallow default as a pool id
            'default': pool.response_pool_id
        }
        ruleset.add_response_pool(pool.response_pool_id)

        # Get our monitor
        monitor_id = self._traffic_director_monitor(new).dsf_monitor_id

        # Make sure we have all the pools we're going to need
        for _id, pool in sorted(new.dynamic.pools.items()):
            values = [{
                'weight': v.get('weight', 1),
                'value': v['value'],
            } for v in pool.data['values']]
            pool = self._find_or_create_dynamic_pool(td, pools, _id,
                                                     new._type, values,
                                                     monitor_id)
            active_pools[_id] = pool.response_pool_id

        # Run through and configure our rules
        for rule_num, rule in enumerate(reversed(new.dynamic.rules)):
            criteria = defaultdict(lambda: defaultdict(list))
            criteria_type = 'always'
            try:
                geos = rule.data['geos']
                criteria_type = 'geoip'
            except KeyError:
                geos = []

            for geo in geos:
                geo = GeoCodes.parse(geo)
                if geo['province_code']:
                    criteria['geoip']['province'] \
                        .append(geo['province_code'].lower())
                elif geo['country_code']:
                    criteria['geoip']['country'] \
                        .append(geo['country_code'])
                else:
                    criteria['geoip']['region'] \
                        .append(self.REGION_CODES[geo['continent_code']])

            label = '{}:{}'.format(rule_num, uuid4().hex)
            ruleset = DSFRuleset(label, criteria_type, [], criteria)
            # Something you have to call create others the constructor does it
            ruleset.create(td, index=insert_at)

            # Add the primary pool for this rule
            rule_pool = rule.data['pool']
            ruleset.add_response_pool(active_pools[rule_pool])

            # OK, we have the rule and its primary pool setup, now look to see
            # if there's a fallback chain that needs to be configured
            fallback = new.dynamic.pools[rule_pool].data.get('fallback', None)
            seen = set([rule_pool])
            while fallback and fallback not in seen:
                seen.add(fallback)
                # looking at client lib code, index > exists appends
                ruleset.add_response_pool(active_pools[fallback], index=999)
                fallback = new.dynamic.pools[fallback].data.get('fallback',
                                                                None)
            if fallback is not None:
                # If we're out of the while and fallback is not None that means
                # there was a loop. This generally shouldn't happen since
                # Record validations test for it, but this is a
                # belt-and-suspenders setup. Excepting here would put things
                # into a partially configured state which would be bad. We'll
                # just break at the point where the loop was going to happen
                # and log about it. Note that any time we hit this we're likely
                # to hit it multiple times as we configure the other pools
                self.log.warn('_mod_dynamic_rulesets: loop detected in '
                              'fallback chain, fallback=%s, seen=%s', fallback,
                              seen)

            # and always add default as the last
            ruleset.add_response_pool(active_pools['default'], index=999)

        # we're done with active_pools as a lookup, convert it in to a set of
        # the ids in use
        active_pools = set(active_pools.values())
        # Clean up unused response_pools
        for pool in pools:
            if pool.response_pool_id in active_pools:
                continue
            pool.delete()

        # Clean out the old rulesets
        for ruleset in existing_rulesets:
            ruleset.delete()

    def _mod_dynamic_Create(self, dyn_zone, change):
        new = change.new
        fqdn = new.fqdn
        _type = new._type
        # Create a new traffic director
        label = '{}:{}'.format(fqdn, _type)
        node = DSFNode(new.zone.name, fqdn)
        td = TrafficDirector(label, ttl=new.ttl, nodes=[node], publish='Y')
        self.log.debug('_mod_dynamic_Create: td=%s', td.service_id)
        # Sync up it's pools & rules
        self._mod_dynamic_rulesets(td, change)
        # Store it for future reference
        self.traffic_directors[fqdn] = {
            _type: td
        }

    def _mod_dynamic_Update(self, dyn_zone, change):
        new = change.new
        if not new.dynamic:
            if new.geo:
                # New record is a geo record
                self.log.info('_mod_dynamic_Update: %s to geo', new.fqdn)
                # Convert the TD over to a geo and we're done
                self._mod_geo_Update(dyn_zone, change)
            else:
                # New record doesn't have dynamic, we're going from a TD to a
                # regular record
                self.log.info('_mod_dynamic_Update: %s to plain', new.fqdn)
                # Create the regular record
                self._mod_Create(dyn_zone, change)
                # Delete the dynamic
                self._mod_dynamic_Delete(dyn_zone, change)
            return
        try:
            # We'll be dynamic going forward, see if we have one already
            td = self.traffic_directors[new.fqdn][new._type]
            if change.existing.geo:
                self.log.info('_mod_dynamic_Update: %s from geo', new.fqdn)
            else:
                self.log.debug('_mod_dynamic_Update: %s existing', new.fqdn)
            # If we're here we do, we'll just update it down below
        except KeyError:
            # There's no td, this is actually a create, we must be going from a
            # non-dynamic to dynamic record
            # First create the dynamic record
            self.log.info('_mod_dynamic_Update: %s from regular', new.fqdn)
            self._mod_dynamic_Create(dyn_zone, change)
            # From a generic so remove the old generic
            self._mod_Delete(dyn_zone, change)
            return

        # IF we're here it's actually an update, sync up rules
        self._mod_dynamic_rulesets(td, change)

    def _mod_dynamic_Delete(self, dyn_zone, change):
        existing = change.existing
        fqdn_tds = self.traffic_directors[existing.fqdn]
        _type = existing._type
        fqdn_tds[_type].delete()
        del fqdn_tds[_type]

    def _mod_Create(self, dyn_zone, change):
        new = change.new
        kwargs_for = getattr(self, '_kwargs_for_{}'.format(new._type))
        for kwargs in kwargs_for(new):
            dyn_zone.add_record(new.name, new._type, **kwargs)

    def _mod_Delete(self, dyn_zone, change):
        existing = change.existing
        if existing.name:
            target = '{}.{}'.format(existing.name, existing.zone.name[:-1])
        else:
            target = existing.zone.name[:-1]
        _type = self.TYPE_TO_RECORDS[existing._type]
        for rec in dyn_zone.get_all_records()[_type]:
            if rec.fqdn == target:
                rec.delete()

    def _mod_Update(self, dyn_zone, change):
        self._mod_Delete(dyn_zone, change)
        self._mod_Create(dyn_zone, change)

    def _apply_traffic_directors(self, desired, changes, dyn_zone):
        self.log.debug('_apply_traffic_directors: zone=%s', desired.name)
        unhandled_changes = []
        for c in changes:
            # we only mess with changes that have geo info somewhere
            if getattr(c.new, 'dynamic', False) or getattr(c.existing,
                                                           'dynamic', False):
                mod = getattr(self, '_mod_dynamic_{}'
                              .format(c.__class__.__name__))
                mod(dyn_zone, c)
            elif getattr(c.new, 'geo', False) or getattr(c.existing, 'geo',
                                                         False):
                mod = getattr(self, '_mod_geo_{}'.format(c.__class__.__name__))
                mod(dyn_zone, c)
            else:
                unhandled_changes.append(c)

        return unhandled_changes

    def _apply_regular(self, desired, changes, dyn_zone):
        self.log.debug('_apply_regular: zone=%s', desired.name)
        for c in changes:
            mod = getattr(self, '_mod_{}'.format(c.__class__.__name__))
            mod(dyn_zone, c)

    # TODO: detect "extra" changes when monitors are out of date or failover
    # chains are wrong etc.

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        self.log.debug('_apply: zone=%s, len(changes)=%d', desired.name,
                       len(changes))

        self._check_dyn_sess()

        dyn_zone = _CachingDynZone.get(desired.name[:-1], create=True)

        if self.traffic_directors_enabled:
            # any changes left over don't involve geo
            changes = self._apply_traffic_directors(desired, changes, dyn_zone)

        self._apply_regular(desired, changes, dyn_zone)

        dyn_zone.publish()
