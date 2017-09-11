#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from StringIO import StringIO
from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from os import environ
import logging

from .provider.base import BaseProvider
from .provider.yaml import YamlProvider
from .record import Record
from .yaml import safe_load
from .zone import Zone


class _AggregateTarget(object):
    id = 'aggregate'

    def __init__(self, targets):
        self.targets = targets

    def supports(self, record):
        for target in self.targets:
            if not target.supports(record):
                return False
        return True

    @property
    def SUPPORTS_GEO(self):
        for target in self.targets:
            if not target.SUPPORTS_GEO:
                return False
        return True


class MakeThreadFuture(object):

    def __init__(self, func, args, kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def result(self):
        return self.func(*self.args, **self.kwargs)


class MainThreadExecutor(object):
    '''
    Dummy executor that runs things on the main thread during the involcation
    of submit, but still returns a future object with the result. This allows
    code to be written to handle async, even in the case where we don't want to
    use multiple threads/workers and would prefer that things flow as if
    traditionally written.
    '''

    def submit(self, func, *args, **kwargs):
        return MakeThreadFuture(func, args, kwargs)


class Manager(object):
    log = logging.getLogger('Manager')

    def __init__(self, config_file, max_workers=None, include_meta=False):
        self.log.info('__init__: config_file=%s', config_file)

        # Read our config file
        with open(config_file, 'r') as fh:
            self.config = safe_load(fh, enforce_order=False)

        manager_config = self.config.get('manager', {})
        max_workers = manager_config.get('max_workers', 1) \
            if max_workers is None else max_workers
        self.log.info('__init__:   max_workers=%d', max_workers)
        if max_workers > 1:
            self._executor = ThreadPoolExecutor(max_workers=max_workers)
        else:
            self._executor = MainThreadExecutor()

        self.include_meta = include_meta or manager_config.get('include_meta',
                                                               False)
        self.log.info('__init__:   max_workers=%s', self.include_meta)

        self.log.debug('__init__:   configuring providers')
        self.providers = {}
        for provider_name, provider_config in self.config['providers'].items():
            # Get our class and remove it from the provider_config
            try:
                _class = provider_config.pop('class')
            except KeyError:
                self.log.exception('Invalid provider class')
                raise Exception('Provider {} is missing class'
                                .format(provider_name))
            _class = self._get_provider_class(_class)
            # Build up the arguments we need to pass to the provider
            kwargs = {}
            for k, v in provider_config.items():
                try:
                    if v.startswith('env/'):
                        try:
                            env_var = v[4:]
                            v = environ[env_var]
                        except KeyError:
                            self.log.exception('Invalid provider config')
                            raise Exception('Incorrect provider config, '
                                            'missing env var {}'
                                            .format(env_var))
                except AttributeError:
                    pass
                kwargs[k] = v
            try:
                self.providers[provider_name] = _class(provider_name, **kwargs)
            except TypeError:
                self.log.exception('Invalid provider config')
                raise Exception('Incorrect provider config for {}'
                                .format(provider_name))

        zone_tree = {}
        # sort by reversed strings so that parent zones always come first
        for name in sorted(self.config['zones'].keys(), key=lambda s: s[::-1]):
            # ignore trailing dots, and reverse
            pieces = name[:-1].split('.')[::-1]
            # where starts out at the top
            where = zone_tree
            # for all the pieces
            for piece in pieces:
                try:
                    where = where[piece]
                    # our current piece already exists, just point where at
                    # it's value
                except KeyError:
                    # our current piece doesn't exist, create it
                    where[piece] = {}
                    # and then point where at it's newly created value
                    where = where[piece]
        self.zone_tree = zone_tree

    def _get_provider_class(self, _class):
        try:
            module_name, class_name = _class.rsplit('.', 1)
            module = import_module(module_name)
        except (ImportError, ValueError):
            self.log.exception('_get_provider_class: Unable to import '
                               'module %s', _class)
            raise Exception('Unknown provider class: {}'.format(_class))
        try:
            return getattr(module, class_name)
        except AttributeError:
            self.log.exception('_get_provider_class: Unable to get class %s '
                               'from module %s', class_name, module)
            raise Exception('Unknown provider class: {}'.format(_class))

    def configured_sub_zones(self, zone_name):
        # Reversed pieces of the zone name
        pieces = zone_name[:-1].split('.')[::-1]
        # Point where at the root of the tree
        where = self.zone_tree
        # Until we've hit the bottom of this zone
        try:
            while pieces:
                # Point where at the value of our current piece
                where = where[pieces.pop(0)]
        except KeyError:
            self.log.debug('configured_sub_zones: unknown zone, %s, no subs',
                           zone_name)
            return set()
        # We're not pointed at the dict for our name, the keys of which will be
        # any subzones
        sub_zone_names = where.keys()
        self.log.debug('configured_sub_zones: subs=%s', sub_zone_names)
        return set(sub_zone_names)

    def _populate_and_plan(self, zone_name, sources, targets):

        self.log.debug('sync:   populating, zone=%s', zone_name)
        zone = Zone(zone_name,
                    sub_zones=self.configured_sub_zones(zone_name))
        for source in sources:
            source.populate(zone)

        self.log.debug('sync:   planning, zone=%s', zone_name)
        plans = []

        for target in targets:
            if self.include_meta:
                meta = Record.new(zone, 'octodns-meta', {
                    'type': 'TXT',
                    'ttl': 60,
                    'value': 'provider={}'.format(target.id)
                })
                zone.add_record(meta, replace=True)
            plan = target.plan(zone)
            if plan:
                plans.append((target, plan))

        return plans

    def sync(self, eligible_zones=[], eligible_targets=[], dry_run=True,
             force=False):
        self.log.info('sync: eligible_zones=%s, eligible_targets=%s, '
                      'dry_run=%s, force=%s', eligible_zones, eligible_targets,
                      dry_run, force)

        zones = self.config['zones'].items()
        if eligible_zones:
            zones = filter(lambda d: d[0] in eligible_zones, zones)

        futures = []
        for zone_name, config in zones:
            self.log.info('sync:   zone=%s', zone_name)
            try:
                sources = config['sources']
            except KeyError:
                raise Exception('Zone {} is missing sources'.format(zone_name))

            try:
                targets = config['targets']
            except KeyError:
                raise Exception('Zone {} is missing targets'.format(zone_name))
            if eligible_targets:
                targets = filter(lambda d: d in eligible_targets, targets)

            if not targets:
                # Don't bother planning (and more importantly populating) zones
                # when we don't have any eligible targets, waste of
                # time/resources
                self.log.info('sync:   no eligible targets, skipping')
                continue

            self.log.info('sync:   sources=%s -> targets=%s', sources, targets)

            try:
                sources = [self.providers[source] for source in sources]
            except KeyError:
                raise Exception('Zone {}, unknown source: {}'.format(zone_name,
                                                                     source))

            try:
                trgs = []
                for target in targets:
                    trg = self.providers[target]
                    if not isinstance(trg, BaseProvider):
                        raise Exception('{} - "{}" does not support targeting'
                                        .format(trg, target))
                    trgs.append(trg)
                targets = trgs
            except KeyError:
                raise Exception('Zone {}, unknown target: {}'.format(zone_name,
                                                                     target))

            futures.append(self._executor.submit(self._populate_and_plan,
                                                 zone_name, sources, targets))

        # Wait on all results and unpack/flatten them in to a list of target &
        # plan pairs.
        plans = [p for f in futures for p in f.result()]

        hr = '*************************************************************' \
            '*******************\n'
        buf = StringIO()
        buf.write('\n')
        if plans:
            current_zone = None
            for target, plan in plans:
                if plan.desired.name != current_zone:
                    current_zone = plan.desired.name
                    buf.write(hr)
                    buf.write('* ')
                    buf.write(current_zone)
                    buf.write('\n')
                    buf.write(hr)

                buf.write('* ')
                buf.write(target.id)
                buf.write(' (')
                buf.write(target)
                buf.write(')\n*   ')
                for change in plan.changes:
                    buf.write(change.__repr__(leader='* '))
                    buf.write('\n*   ')

                buf.write('Summary: ')
                buf.write(plan)
                buf.write('\n')
        else:
            buf.write(hr)
            buf.write('No changes were planned\n')
        buf.write(hr)
        buf.write('\n')
        self.log.info(buf.getvalue())

        if not force:
            self.log.debug('sync:   checking safety')
            for target, plan in plans:
                plan.raise_if_unsafe()

        if dry_run:
            return 0

        total_changes = 0
        self.log.debug('sync:   applying')
        zones = self.config['zones']
        for target, plan in plans:
            zone_name = plan.existing.name
            if zones[zone_name].get('always-dry-run', False):
                self.log.info('sync: zone=%s skipping always-dry-run',
                              zone_name)
                continue
            total_changes += target.apply(plan)

        self.log.info('sync:   %d total changes', total_changes)
        return total_changes

    def compare(self, a, b, zone):
        '''
        Compare zone data between 2 sources.

        Note: only things supported by both sources will be considered
        '''
        self.log.info('compare: a=%s, b=%s, zone=%s', a, b, zone)

        try:
            a = [self.providers[source] for source in a]
            b = [self.providers[source] for source in b]
        except KeyError as e:
            raise Exception('Unknown source: {}'.format(e.args[0]))

        sub_zones = self.configured_sub_zones(zone)
        za = Zone(zone, sub_zones)
        for source in a:
            source.populate(za)

        zb = Zone(zone, sub_zones)
        for source in b:
            source.populate(zb)

        return zb.changes(za, _AggregateTarget(a + b))

    def dump(self, zone, output_dir, lenient, source, *sources):
        '''
        Dump zone data from the specified source
        '''
        self.log.info('dump: zone=%s, sources=%s', zone, sources)

        # We broke out source to force at least one to be passed, add it to any
        # others we got.
        sources = [source] + list(sources)

        try:
            sources = [self.providers[s] for s in sources]
        except KeyError as e:
            raise Exception('Unknown source: {}'.format(e.args[0]))

        target = YamlProvider('dump', output_dir)

        zone = Zone(zone, self.configured_sub_zones(zone))
        for source in sources:
            source.populate(zone, lenient=lenient)

        plan = target.plan(zone)
        target.apply(plan)

    def validate_configs(self):
        for zone_name, config in self.config['zones'].items():
            zone = Zone(zone_name, self.configured_sub_zones(zone_name))

            try:
                sources = config['sources']
            except KeyError:
                raise Exception('Zone {} is missing sources'.format(zone_name))

            try:
                sources = [self.providers[source] for source in sources]
            except KeyError:
                raise Exception('Zone {}, unknown source: {}'.format(zone_name,
                                                                     source))

            for source in sources:
                if isinstance(source, YamlProvider):
                    source.populate(zone)
