#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from os import environ
from six import text_type
import logging

from .provider.base import BaseProvider
from .provider.plan import Plan
from .provider.yaml import SplitYamlProvider, YamlProvider
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
    def SUPPORTS_ROOT_NS(self):
        for target in self.targets:
            if not target.SUPPORTS_ROOT_NS:
                return False
        return True

    @property
    def SUPPORTS_GEO(self):
        for target in self.targets:
            if not target.SUPPORTS_GEO:
                return False
        return True

    @property
    def SUPPORTS_DYNAMIC(self):
        for target in self.targets:
            if not target.SUPPORTS_DYNAMIC:
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
    Dummy executor that runs things on the main thread during the invocation
    of submit, but still returns a future object with the result. This allows
    code to be written to handle async, even in the case where we don't want to
    use multiple threads/workers and would prefer that things flow as if
    traditionally written.
    '''

    def submit(self, func, *args, **kwargs):
        return MakeThreadFuture(func, args, kwargs)


class ManagerException(Exception):
    pass


class Manager(object):
    log = logging.getLogger('Manager')

    @classmethod
    def _plan_keyer(cls, p):
        plan = p[1]
        return len(plan.changes[0].record.zone.name) if plan.changes else 0

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
        self.log.info('__init__:   include_meta=%s', self.include_meta)

        self.log.debug('__init__:   configuring providers')
        self.providers = {}
        for provider_name, provider_config in self.config['providers'].items():
            # Get our class and remove it from the provider_config
            try:
                _class = provider_config.pop('class')
            except KeyError:
                self.log.exception('Invalid provider class')
                raise ManagerException('Provider {} is missing class'
                                       .format(provider_name))
            _class = self._get_named_class('provider', _class)
            kwargs = self._build_kwargs(provider_config)
            try:
                self.providers[provider_name] = _class(provider_name, **kwargs)
            except TypeError:
                self.log.exception('Invalid provider config')
                raise ManagerException('Incorrect provider config for {}'
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

        self.plan_outputs = {}
        plan_outputs = manager_config.get('plan_outputs', {
            'logger': {
                'class': 'octodns.provider.plan.PlanLogger',
                'level': 'info'
            }
        })
        for plan_output_name, plan_output_config in plan_outputs.items():
            try:
                _class = plan_output_config.pop('class')
            except KeyError:
                self.log.exception('Invalid plan_output class')
                raise ManagerException('plan_output {} is missing class'
                                       .format(plan_output_name))
            _class = self._get_named_class('plan_output', _class)
            kwargs = self._build_kwargs(plan_output_config)
            try:
                self.plan_outputs[plan_output_name] = \
                    _class(plan_output_name, **kwargs)
            except TypeError:
                self.log.exception('Invalid plan_output config')
                raise ManagerException('Incorrect plan_output config for {}'
                                       .format(plan_output_name))

    def _get_named_class(self, _type, _class):
        try:
            module_name, class_name = _class.rsplit('.', 1)
            module = import_module(module_name)
        except (ImportError, ValueError):
            self.log.exception('_get_{}_class: Unable to import '
                               'module %s', _class)
            raise ManagerException('Unknown {} class: {}'
                                   .format(_type, _class))
        try:
            return getattr(module, class_name)
        except AttributeError:
            self.log.exception('_get_{}_class: Unable to get class %s '
                               'from module %s', class_name, module)
            raise ManagerException('Unknown {} class: {}'
                                   .format(_type, _class))

    def _build_kwargs(self, source):
        # Build up the arguments we need to pass to the provider
        kwargs = {}
        for k, v in source.items():
            try:
                if v.startswith('env/'):
                    try:
                        env_var = v[4:]
                        v = environ[env_var]
                    except KeyError:
                        self.log.exception('Invalid provider config')
                        raise ManagerException('Incorrect provider config, '
                                               'missing env var {}'
                                               .format(env_var))
            except AttributeError:
                pass
            kwargs[k] = v

        return kwargs

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

    def _populate_and_plan(self, zone_name, sources, targets, lenient=False):

        self.log.debug('sync:   populating, zone=%s, lenient=%s',
                       zone_name, lenient)
        zone = Zone(zone_name,
                    sub_zones=self.configured_sub_zones(zone_name))
        for source in sources:
            try:
                source.populate(zone, lenient=lenient)
            except TypeError as e:
                if "keyword argument 'lenient'" not in text_type(e):
                    raise
                self.log.warn(': provider %s does not accept lenient param',
                              source.__class__.__name__)
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
            zones = [z for z in zones if z[0] in eligible_zones]

        futures = []
        for zone_name, config in zones:
            self.log.info('sync:   zone=%s', zone_name)
            lenient = config.get('lenient', False)
            try:
                sources = config['sources']
            except KeyError:
                raise ManagerException('Zone {} is missing sources'
                                       .format(zone_name))

            try:
                targets = config['targets']
            except KeyError:
                raise ManagerException('Zone {} is missing targets'
                                       .format(zone_name))
            if eligible_targets:
                targets = [t for t in targets if t in eligible_targets]

            if not targets:
                # Don't bother planning (and more importantly populating) zones
                # when we don't have any eligible targets, waste of
                # time/resources
                self.log.info('sync:   no eligible targets, skipping')
                continue

            self.log.info('sync:   sources=%s -> targets=%s', sources, targets)

            try:
                # rather than using a list comprehension, we break this loop
                # out so that the `except` block below can reference the
                # `source`
                collected = []
                for source in sources:
                    collected.append(self.providers[source])
                sources = collected
            except KeyError:
                raise ManagerException('Zone {}, unknown source: {}'
                                       .format(zone_name, source))

            try:
                trgs = []
                for target in targets:
                    trg = self.providers[target]
                    if not isinstance(trg, BaseProvider):
                        raise ManagerException('{} - "{}" does not support '
                                               'targeting'.format(trg, target))
                    trgs.append(trg)
                targets = trgs
            except KeyError:
                raise ManagerException('Zone {}, unknown target: {}'
                                       .format(zone_name, target))

            futures.append(self._executor.submit(self._populate_and_plan,
                                                 zone_name, sources,
                                                 targets, lenient=lenient))

        # Wait on all results and unpack/flatten them in to a list of target &
        # plan pairs.
        plans = [p for f in futures for p in f.result()]

        # Best effort sort plans children first so that we create/update
        # children zones before parents which should allow us to more safely
        # extract things into sub-zones. Combining a child back into a parent
        # can't really be done all that safely in general so we'll optimize for
        # this direction.
        plans.sort(key=self._plan_keyer, reverse=True)

        for output in self.plan_outputs.values():
            output.run(plans=plans, log=self.log)

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
            raise ManagerException('Unknown source: {}'.format(e.args[0]))

        sub_zones = self.configured_sub_zones(zone)
        za = Zone(zone, sub_zones)
        for source in a:
            source.populate(za)

        zb = Zone(zone, sub_zones)
        for source in b:
            source.populate(zb)

        return zb.changes(za, _AggregateTarget(a + b))

    def dump(self, zone, output_dir, lenient, split, source, *sources):
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
            raise ManagerException('Unknown source: {}'.format(e.args[0]))

        clz = YamlProvider
        if split:
            clz = SplitYamlProvider
        target = clz('dump', output_dir)

        zone = Zone(zone, self.configured_sub_zones(zone))
        for source in sources:
            source.populate(zone, lenient=lenient)

        plan = target.plan(zone)
        if plan is None:
            plan = Plan(zone, zone, [], False)
        target.apply(plan)

    def validate_configs(self):
        for zone_name, config in self.config['zones'].items():
            zone = Zone(zone_name, self.configured_sub_zones(zone_name))

            try:
                sources = config['sources']
            except KeyError:
                raise ManagerException('Zone {} is missing sources'
                                       .format(zone_name))

            try:
                # rather than using a list comprehension, we break this loop
                # out so that the `except` block below can reference the
                # `source`
                collected = []
                for source in sources:
                    collected.append(self.providers[source])
                sources = collected
            except KeyError:
                raise ManagerException('Zone {}, unknown source: {}'
                                       .format(zone_name, source))

            for source in sources:
                if isinstance(source, YamlProvider):
                    source.populate(zone)
