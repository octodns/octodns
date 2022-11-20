#
#
#

from collections import deque
from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from logging import getLogger
from os import environ
from sys import stdout

from . import __VERSION__
from .idna import IdnaDict, idna_decode, idna_encode
from .provider.base import BaseProvider
from .provider.plan import Plan
from .provider.yaml import SplitYamlProvider, YamlProvider
from .record import Record
from .yaml import safe_load
from .zone import Zone


# TODO: this can go away once we no longer support python 3.7
try:
    from importlib.metadata import (
        PackageNotFoundError,
        version as module_version,
    )
except ModuleNotFoundError:  # pragma: no cover

    class PackageNotFoundError(Exception):
        pass

    def module_version(*args, **kargs):
        raise PackageNotFoundError('placeholder')


class _AggregateTarget(object):
    id = 'aggregate'

    def __init__(self, targets):
        self.targets = targets
        self.SUPPORTS = targets[0].SUPPORTS
        for target in targets[1:]:
            self.SUPPORTS = self.SUPPORTS & target.SUPPORTS

    def supports(self, record):
        for target in self.targets:
            if not target.supports(record):
                return False
        return True

    def __getattr__(self, name):
        if name.startswith('SUPPORTS_'):
            # special case to handle any current or future SUPPORTS_* by
            # returning whether all providers support the requested
            # functionality.
            for target in self.targets:
                if not getattr(target, name):
                    return False
            return True
        klass = self.__class__.__name__
        raise AttributeError(f'{klass} object has no attribute {name}')


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
    log = getLogger('Manager')
    plan_log = getLogger('Plan')

    @classmethod
    def _plan_keyer(cls, p):
        plan = p[1]
        return len(plan.changes[0].record.zone.name) if plan.changes else 0

    # TODO: all of this should get broken up, mainly so that it's not so huge
    # and each bit can be cleanly tested independently
    def __init__(self, config_file, max_workers=None, include_meta=False):
        version = self._try_version('octodns', version=__VERSION__)
        self.log.info(
            '__init__: config_file=%s (octoDNS %s)', config_file, version
        )

        self._configured_sub_zones = None

        # Read our config file
        with open(config_file, 'r') as fh:
            self.config = safe_load(fh, enforce_order=False)

        zones = self.config['zones']
        self.config['zones'] = self._config_zones(zones)

        manager_config = self.config.get('manager', {})
        self._executor = self._config_executor(manager_config, max_workers)
        self.include_meta = self._config_include_meta(
            manager_config, include_meta
        )

        self.global_processors = manager_config.get('processors', [])
        self.log.info('__init__: global_processors=%s', self.global_processors)

        providers_config = self.config['providers']
        self.providers = self._config_providers(providers_config)

        processors_config = self.config.get('processors', {})
        self.processors = self._config_processors(processors_config)

        plan_outputs_config = manager_config.get(
            'plan_outputs',
            {
                '_logger': {
                    'class': 'octodns.provider.plan.PlanLogger',
                    'level': 'info',
                }
            },
        )
        self.plan_outputs = self._config_plan_outputs(plan_outputs_config)

    def _config_zones(self, zones):
        # record the set of configured zones we have as they are
        configured_zones = set([z.lower() for z in zones.keys()])
        # walk the configured zones
        for name in configured_zones:
            if 'xn--' not in name:
                continue
            # this is an IDNA format zone name
            decoded = idna_decode(name)
            # do we also have a config for its utf-8
            if decoded in configured_zones:
                raise ManagerException(
                    f'"{decoded}" configured both in utf-8 and idna "{name}"'
                )

        # convert the zones portion of things into an IdnaDict
        return IdnaDict(zones)

    def _config_executor(self, manager_config, max_workers=None):
        max_workers = (
            manager_config.get('max_workers', 1)
            if max_workers is None
            else max_workers
        )
        self.log.info('_config_executor: max_workers=%d', max_workers)
        if max_workers > 1:
            return ThreadPoolExecutor(max_workers=max_workers)
        return MainThreadExecutor()

    def _config_include_meta(self, manager_config, include_meta=False):
        include_meta = include_meta or manager_config.get('include_meta', False)
        self.log.info('_config_include_meta: include_meta=%s', include_meta)
        return include_meta

    def _config_providers(self, providers_config):
        self.log.debug('_config_providers: configuring providers')
        providers = {}
        for provider_name, provider_config in providers_config.items():
            # Get our class and remove it from the provider_config
            try:
                _class = provider_config.pop('class')
            except KeyError:
                self.log.exception('Invalid provider class')
                raise ManagerException(
                    f'Provider {provider_name} is missing class'
                )
            _class, module, version = self._get_named_class('provider', _class)
            kwargs = self._build_kwargs(provider_config)
            try:
                providers[provider_name] = _class(provider_name, **kwargs)
                self.log.info(
                    '__init__: provider=%s (%s %s)',
                    provider_name,
                    module,
                    version,
                )
            except TypeError:
                self.log.exception('Invalid provider config')
                raise ManagerException(
                    'Incorrect provider config for ' + provider_name
                )

        return providers

    def _config_processors(self, processors_config):
        processors = {}
        for processor_name, processor_config in processors_config.items():
            try:
                _class = processor_config.pop('class')
            except KeyError:
                self.log.exception('Invalid processor class')
                raise ManagerException(
                    f'Processor {processor_name} is missing class'
                )
            _class, module, version = self._get_named_class('processor', _class)
            kwargs = self._build_kwargs(processor_config)
            try:
                processors[processor_name] = _class(processor_name, **kwargs)
                self.log.info(
                    '__init__: processor=%s (%s %s)',
                    processor_name,
                    module,
                    version,
                )
            except TypeError:
                self.log.exception('Invalid processor config')
                raise ManagerException(
                    'Incorrect processor config for ' + processor_name
                )
        return processors

    def _config_plan_outputs(self, plan_outputs_config):
        plan_outputs = {}
        for plan_output_name, plan_output_config in plan_outputs_config.items():
            try:
                _class = plan_output_config.pop('class')
            except KeyError:
                self.log.exception('Invalid plan_output class')
                raise ManagerException(
                    f'plan_output {plan_output_name} is missing class'
                )
            _class, module, version = self._get_named_class(
                'plan_output', _class
            )
            kwargs = self._build_kwargs(plan_output_config)
            try:
                plan_outputs[plan_output_name] = _class(
                    plan_output_name, **kwargs
                )
                # Don't print out version info for the default output
                if plan_output_name != '_logger':
                    self.log.info(
                        '__init__: plan_output=%s (%s %s)',
                        plan_output_name,
                        module,
                        version,
                    )
            except TypeError:
                self.log.exception('Invalid plan_output config')
                raise ManagerException(
                    'Incorrect plan_output config for ' + plan_output_name
                )
        return plan_outputs

    def _try_version(self, module_name, module=None, version=None):
        try:
            # Always try and use the official lookup first
            return module_version(module_name)
        except PackageNotFoundError:
            pass
        # If we were passed a version that's next in line
        if version is not None:
            return version
        # finally try and import the module and see if it has a __VERSION__
        if module is None:
            module = import_module(module_name)
        return getattr(module, '__VERSION__', None)

    def _import_module(self, module_name):
        current = module_name
        _next = current.rsplit('.', 1)[0]
        module = import_module(current)
        version = self._try_version(current, module=module)
        # If we didn't find a version in the specific module we're importing,
        # we'll try walking up the hierarchy, as long as there is one (`.`),
        # looking for it.
        while version is None and current != _next:
            current = _next
            _next = current.rsplit('.', 1)[0]
            version = self._try_version(current)
        return module, version or 'n/a'

    def _get_named_class(self, _type, _class):
        try:
            module_name, class_name = _class.rsplit('.', 1)
            module, version = self._import_module(module_name)
        except (ImportError, ValueError):
            self.log.exception(
                '_get_{}_class: Unable to import module %s', _class
            )
            raise ManagerException(f'Unknown {_type} class: {_class}')

        try:
            return getattr(module, class_name), module_name, version
        except AttributeError:
            self.log.exception(
                '_get_{}_class: Unable to get class %s from module %s',
                class_name,
                module,
            )
            raise ManagerException(f'Unknown {_type} class: {_class}')

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
                        raise ManagerException(
                            'Incorrect provider config, '
                            'missing env var ' + env_var
                        )
            except AttributeError:
                pass
            kwargs[k] = v

        return kwargs

    def configured_sub_zones(self, zone_name):
        '''
        Accepts either UTF-8 or IDNA encoded zone name and returns the list of
        any configured sub-zones in IDNA form. E.g. for the following
        configured zones:
          some.com.
          other.some.com.
          deep.thing.some.com.
        It would return
          other
          deep.thing
        '''
        if self._configured_sub_zones is None:
            # First time through we compute all the sub-zones

            configured_sub_zones = IdnaDict()

            # Get a list of all of our zone names. Sort them from shortest to
            # longest so that parents will always come before their subzones
            zones = sorted(
                self.config['zones'].keys(), key=lambda z: len(z), reverse=True
            )
            zones = deque(zones)
            # Until we're done processing zones
            while zones:
                # Grab the one we'lre going to work on now
                zone = zones.pop()
                dotted = f'.{zone}'
                trimmer = len(dotted)
                subs = set()
                # look at all the zone names that come after it
                for candidate in zones:
                    # If they end with this zone's dotted name, it's a sub
                    if candidate.endswith(dotted):
                        # We want subs to exclude the zone portion
                        subs.add(candidate[:-trimmer])

                configured_sub_zones[zone] = subs

            self._configured_sub_zones = configured_sub_zones

        return self._configured_sub_zones.get(zone_name, set())

    def _populate_and_plan(
        self,
        zone_name,
        processors,
        sources,
        targets,
        desired=None,
        lenient=False,
    ):

        zone = self.get_zone(zone_name)
        self.log.debug(
            'sync:   populating, zone=%s, lenient=%s',
            zone.decoded_name,
            lenient,
        )

        if desired:
            # This is an alias zone, rather than populate it we'll copy the
            # records over from `desired`.
            for _, records in desired._records.items():
                for record in records:
                    zone.add_record(record.copy(zone=zone), lenient=lenient)
        else:
            for source in sources:
                try:
                    source.populate(zone, lenient=lenient)
                except TypeError as e:
                    if "unexpected keyword argument 'lenient'" not in str(e):
                        raise
                    self.log.warning(
                        'provider %s does not accept lenient param',
                        source.__class__.__name__,
                    )
                    source.populate(zone)

        for processor in processors:
            zone = processor.process_source_zone(zone, sources=sources)

        self.log.debug('sync:   planning, zone=%s', zone.decoded_name)
        plans = []

        for target in targets:
            if self.include_meta:
                meta = Record.new(
                    zone,
                    'octodns-meta',
                    {
                        'type': 'TXT',
                        'ttl': 60,
                        'value': f'provider={target.id}',
                    },
                )
                zone.add_record(meta, replace=True)
            try:
                plan = target.plan(zone, processors=processors)
            except TypeError as e:
                if "keyword argument 'processors'" not in str(e):
                    raise
                self.log.warning(
                    'provider.plan %s does not accept processors param',
                    target.__class__.__name__,
                )
                plan = target.plan(zone)

            for processor in processors:
                plan = processor.process_plan(
                    plan, sources=sources, target=target
                )
            if plan:
                plans.append((target, plan))

        # Return the zone as it's the desired state
        return plans, zone

    def sync(
        self,
        eligible_zones=[],
        eligible_sources=[],
        eligible_targets=[],
        dry_run=True,
        force=False,
        plan_output_fh=stdout,
    ):

        self.log.info(
            'sync: eligible_zones=%s, eligible_targets=%s, dry_run=%s, '
            'force=%s, plan_output_fh=%s',
            eligible_zones,
            eligible_targets,
            dry_run,
            force,
            getattr(plan_output_fh, 'name', plan_output_fh.__class__.__name__),
        )

        zones = self.config['zones']
        if eligible_zones:
            zones = IdnaDict({n: zones.get(n) for n in eligible_zones})

        aliased_zones = {}
        futures = []
        for zone_name, config in zones.items():
            decoded_zone_name = idna_decode(zone_name)
            self.log.info('sync:   zone=%s', decoded_zone_name)
            if 'alias' in config:
                source_zone = config['alias']

                # Check that the source zone is defined.
                if source_zone not in self.config['zones']:
                    msg = f'Invalid alias zone {decoded_zone_name}: source zone {idna_decode(source_zone)} does not exist'
                    self.log.error(msg)
                    raise ManagerException(msg)

                # Check that the source zone is not an alias zone itself.
                if 'alias' in self.config['zones'][source_zone]:
                    msg = f'Invalid alias zone {decoded_zone_name}: source zone {idna_decode(source_zone)} is an alias zone'
                    self.log.error(msg)
                    raise ManagerException(msg)

                aliased_zones[zone_name] = source_zone
                continue

            lenient = config.get('lenient', False)
            try:
                sources = config['sources']
            except KeyError:
                raise ManagerException(
                    f'Zone {decoded_zone_name} is missing sources'
                )

            try:
                targets = config['targets']
            except KeyError:
                raise ManagerException(
                    f'Zone {decoded_zone_name} is missing targets'
                )

            processors = config.get('processors', [])

            if eligible_sources and not [
                s for s in sources if s in eligible_sources
            ]:
                self.log.info('sync:   no eligible sources, skipping')
                continue

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
                collected = []
                for processor in self.global_processors + processors:
                    collected.append(self.processors[processor])
                processors = collected
            except KeyError:
                raise ManagerException(
                    f'Zone {decoded_zone_name}, unknown '
                    f'processor: {processor}'
                )

            try:
                # rather than using a list comprehension, we break this loop
                # out so that the `except` block below can reference the
                # `source`
                collected = []
                for source in sources:
                    collected.append(self.providers[source])
                sources = collected
            except KeyError:
                raise ManagerException(
                    f'Zone {decoded_zone_name}, unknown ' f'source: {source}'
                )

            try:
                trgs = []
                for target in targets:
                    trg = self.providers[target]
                    if not isinstance(trg, BaseProvider):
                        raise ManagerException(
                            f'{trg} - "{target}" does not support targeting'
                        )
                    trgs.append(trg)
                targets = trgs
            except KeyError:
                raise ManagerException(
                    f'Zone {decoded_zone_name}, unknown ' f'target: {target}'
                )

            futures.append(
                self._executor.submit(
                    self._populate_and_plan,
                    zone_name,
                    processors,
                    sources,
                    targets,
                    lenient=lenient,
                )
            )

        # Wait on all results and unpack/flatten the plans and store the
        # desired states in case we need them below
        plans = []
        desired = {}
        for future in futures:
            ps, d = future.result()
            desired[d.name] = d
            for plan in ps:
                plans.append(plan)

        # Populate aliases zones.
        futures = []
        for zone_name, zone_source in aliased_zones.items():
            source_config = self.config['zones'][zone_source]
            try:
                desired_config = desired[zone_source]
            except KeyError:
                raise ManagerException(
                    f'Zone {idna_decode(zone_name)} cannot be synced '
                    f'without zone {zone_source} sinced '
                    'it is aliased'
                )
            futures.append(
                self._executor.submit(
                    self._populate_and_plan,
                    zone_name,
                    processors,
                    [],
                    [self.providers[t] for t in source_config['targets']],
                    desired=desired_config,
                    lenient=lenient,
                )
            )

        # Wait on results and unpack/flatten the plans, ignore the desired here
        # as these are aliased zones
        plans += [p for f in futures for p in f.result()[0]]

        # Best effort sort plans children first so that we create/update
        # children zones before parents which should allow us to more safely
        # extract things into sub-zones. Combining a child back into a parent
        # can't really be done all that safely in general so we'll optimize for
        # this direction.
        plans.sort(key=self._plan_keyer, reverse=True)

        for output in self.plan_outputs.values():
            output.run(plans=plans, log=self.plan_log, fh=plan_output_fh)

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
            zone_name = plan.existing.decoded_name
            if zones[zone_name].get('always-dry-run', False):
                self.log.info(
                    'sync: zone=%s skipping always-dry-run', zone_name
                )
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
            raise ManagerException(f'Unknown source: {e.args[0]}')

        za = self.get_zone(zone)
        for source in a:
            source.populate(za)

        zb = self.get_zone(zone)
        for source in b:
            source.populate(zb)

        return zb.changes(za, _AggregateTarget(a + b))

    def dump(
        self,
        zone,
        output_dir,
        sources,
        lenient=False,
        split=False,
        output_provider=None,
    ):
        '''
        Dump zone data from the specified source
        '''
        self.log.info(
            'dump: zone=%s, output_dir=%s, output_provider=%s, '
            'lenient=%s, split=%s, sources=%s',
            zone,
            output_dir,
            output_provider,
            lenient,
            split,
            sources,
        )

        try:
            sources = [self.providers[s] for s in sources]
        except KeyError as e:
            raise ManagerException(f'Unknown source: {e.args[0]}')

        if output_provider:
            self.log.info(
                'dump: using specified output_provider=%s', output_provider
            )
            try:
                target = self.providers[output_provider]
            except KeyError as e:
                raise ManagerException(f'Unknown output_provider: {e.args[0]}')
            # The chosen output provider has to support a directory property so
            # that we can tell it where the user has requested the dumped files
            # to reside.
            if not hasattr(target, 'directory'):
                msg = (
                    f'output_provider={output_provider}, does not support '
                    'directory property'
                )
                raise ManagerException(msg)
            if target.directory != output_dir:
                # If the requested target doesn't match what's configured in
                # the chosen provider then we'll need to set it. Before doing
                # that we make a copy of the provider so that it can remain
                # unchanged and potentially be used as a source, e.g. copying
                # from one yaml to another
                if not hasattr(target, 'copy'):
                    msg = (
                        f'output_provider={output_provider}, does not '
                        'support copy method'
                    )
                    raise ManagerException(msg)
                target = target.copy()
                self.log.info(
                    'dump: setting directory of output_provider copy to %s',
                    output_dir,
                )
                target.directory = output_dir
        else:
            self.log.info('dump: using custom YamlProvider')
            clz = YamlProvider
            if split:
                clz = SplitYamlProvider
            target = clz('dump', output_dir)

        zone = self.get_zone(zone)
        for source in sources:
            source.populate(zone, lenient=lenient)

        plan = target.plan(zone)
        if plan is None:
            plan = Plan(zone, zone, [], False)
        target.apply(plan)

    def validate_configs(self):
        # TODO: this code can probably be shared with stuff in sync
        for zone_name, config in self.config['zones'].items():
            decoded_zone_name = idna_decode(zone_name)
            zone = self.get_zone(zone_name)

            source_zone = config.get('alias')
            if source_zone:
                if source_zone not in self.config['zones']:
                    self.log.exception('Invalid alias zone')
                    raise ManagerException(
                        f'Invalid alias zone {decoded_zone_name}: '
                        f'source zone {source_zone} does '
                        'not exist'
                    )

                if 'alias' in self.config['zones'][source_zone]:
                    self.log.exception('Invalid alias zone')
                    raise ManagerException(
                        f'Invalid alias zone {decoded_zone_name}: '
                        'source zone {source_zone} is an '
                        'alias zone'
                    )

                # this is just here to satisfy coverage, see
                # https://github.com/nedbat/coveragepy/issues/198
                source_zone = source_zone
                continue

            lenient = config.get('lenient', False)
            try:
                sources = config['sources']
            except KeyError:
                raise ManagerException(
                    f'Zone {decoded_zone_name} is missing sources'
                )

            try:
                # rather than using a list comprehension, we break this
                # loop out so that the `except` block below can reference
                # the `source`
                collected = []
                for source in sources:
                    collected.append(self.providers[source])
                sources = collected
            except KeyError:
                raise ManagerException(
                    f'Zone {decoded_zone_name}, unknown source: ' + source
                )

            for source in sources:
                if isinstance(source, YamlProvider):
                    source.populate(zone, lenient=lenient)

            # check that processors are in order if any are specified
            processors = config.get('processors', [])
            try:
                # same as above, but for processors this time
                for processor in processors:
                    collected.append(self.processors[processor])
            except KeyError:
                raise ManagerException(
                    f'Zone {decoded_zone_name}, unknown '
                    f'processor: {processor}'
                )

    def get_zone(self, zone_name):
        if not zone_name[-1] == '.':
            raise ManagerException(
                f'Invalid zone name {idna_decode(zone_name)}, missing ending dot'
            )

        zone = self.config['zones'].get(zone_name)
        if zone is not None:
            sub_zones = self.configured_sub_zones(zone_name)
            return Zone(idna_encode(zone_name), sub_zones, config=zone)

        raise ManagerException(f'Unknown zone name {idna_decode(zone_name)}')
