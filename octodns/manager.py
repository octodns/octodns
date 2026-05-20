from __future__ import annotations

from collections import deque
from concurrent.futures import ThreadPoolExecutor
from fnmatch import filter as fnmatch_filter
from hashlib import sha256
from importlib import import_module
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as module_version
from json import dumps
from logging import INFO, Logger, getLogger
from re import Pattern
from re import compile as re_compile
from typing import TYPE_CHECKING, Any, Callable, Iterable, Optional

from . import __version__
from .deprecation import deprecated
from .idna import IdnaDict, idna_decode, idna_encode
from .processor.arpa import AutoArpa
from .processor.meta import MetaProcessor
from .provider.base import BaseProvider
from .provider.plan import Plan
from .provider.yaml import SplitYamlProvider, YamlProvider
from .record import Record
from .record.exception import RecordException
from .record.validator import RecordValidator, ValueValidator
from .secret.environ import EnvironSecrets
from .yaml import safe_load
from .zone import Zone
from .zone.exception import ZoneException
from .zone.validator import ZoneValidator

if TYPE_CHECKING:
    from octodns.provider.plan import _PlanOutput as PlanOutput


class _AggregateTarget:
    id: str = 'aggregate'

    def __init__(self, targets: list[BaseProvider]) -> None:
        self.targets: list[BaseProvider] = targets
        self.SUPPORTS: set[str] = targets[0].SUPPORTS  # type: ignore[attr-defined]
        for target in targets[1:]:
            self.SUPPORTS = self.SUPPORTS & target.SUPPORTS  # type: ignore[attr-defined]

    def supports(self, record: Record) -> bool:
        for target in self.targets:
            if not target.supports(record):  # type: ignore[attr-defined]
                return False
        return True

    def __getattr__(self, name: str) -> bool:
        if name.startswith('SUPPORTS_'):
            # special case to handle any current or future SUPPORTS_* by
            # returning whether all providers support the requested
            # functionality.
            for target in self.targets:
                if not getattr(target, name):  # type: ignore[attr-defined]
                    return False
            return True
        klass = self.__class__.__name__
        raise AttributeError(f'{klass} object has no attribute {name}')


class MakeThreadFuture:
    def __init__(
        self,
        func: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> None:
        self.func: Callable[..., Any] = func
        self.args: tuple[Any, ...] = args
        self.kwargs: dict[str, Any] = kwargs

    def result(self) -> Any:
        return self.func(*self.args, **self.kwargs)


class MainThreadExecutor:
    '''
    Dummy executor that runs things on the main thread during the invocation
    of submit, but still returns a future object with the result. This allows
    code to be written to handle async, even in the case where we don't want to
    use multiple threads/workers and would prefer that things flow as if
    traditionally written.
    '''

    def submit(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> MakeThreadFuture:
        return MakeThreadFuture(func, args, kwargs)


class ManagerException(Exception):
    pass


class Manager:
    log: Logger = getLogger('Manager')
    plan_log: Logger = getLogger('Plan')

    @classmethod
    def _plan_keyer(cls, p: tuple[Any, Plan]) -> int:
        plan = p[1]
        return len(plan.changes[0].record.zone.name) if plan.changes else 0

    def __init__(
        self,
        config_file: str,
        max_workers: Optional[int] = None,
        include_meta: bool = False,
        auto_arpa: bool = False,
        enable_checksum: bool = False,
    ) -> None:
        version = self._try_version('octodns', version=__version__)
        self.log.info(
            '__init__: config_file=%s, (octoDNS %s)', config_file, version
        )

        self._configured_sub_zones: Optional[IdnaDict[str, set[str]]] = None

        # Read our config file
        with open(config_file, 'r') as fh:
            self.config: dict[str, Any] = safe_load(fh, enforce_order=False)

        zones: dict[str, Any] = self.config['zones']
        self.config['zones'] = self._config_zones(zones)

        manager_config: dict[str, Any] = self.config.get('manager') or {}
        self._executor = self._config_executor(manager_config, max_workers)
        self.include_meta: bool = self._config_include_meta(
            manager_config, include_meta
        )
        self.enable_checksum: bool = self._config_enable_checksum(
            manager_config, enable_checksum
        )

        # add our hard-coded environ handler first so that other secret
        # providers can pull in env variables w/it
        self.secret_handlers: dict[str, Any] = {'env': EnvironSecrets('env')}
        secret_handlers_config: dict[str, Any] = (
            self.config.get('secret_handlers') or {}
        )
        self.secret_handlers.update(
            self._config_secret_handlers(secret_handlers_config)
        )

        self.auto_arpa: bool | dict[str, Any] = self._config_auto_arpa(
            manager_config, auto_arpa
        )

        self.global_processors: list[str] = (
            manager_config.get('processors') or []
        )
        self.log.info('__init__: global_processors=%s', self.global_processors)

        self.global_post_processors: list[str] = (
            manager_config.get('post_processors') or []
        )
        self.log.info(
            '__init__: global_post_processors=%s', self.global_post_processors
        )

        providers_config: dict[str, Any] = self.config['providers']
        self.providers: dict[str, BaseProvider] = self._config_providers(
            providers_config
        )

        processors_config: dict[str, Any] = self.config.get('processors') or {}
        self.processors: dict[str, Any] = self._config_processors(
            processors_config
        )

        validators_config: dict[str, Any] = self.config.get('validators') or {}
        self._config_validators(validators_config)
        self._configure_validators(manager_config)

        if self.auto_arpa:
            self.log.info(
                '__init__: adding auto-arpa to processors and providers, prepending it to global_post_processors list'
            )
            kwargs = self.auto_arpa if isinstance(self.auto_arpa, dict) else {}
            auto_arpa_processor = AutoArpa('auto-arpa', **kwargs)
            self.providers[auto_arpa_processor.name] = auto_arpa_processor  # type: ignore[assignment]
            self.processors[auto_arpa_processor.name] = auto_arpa_processor
            self.global_post_processors = [
                auto_arpa_processor.name
            ] + self.global_post_processors

        if self.include_meta:
            self.log.info(
                '__init__: adding meta to processors and providers, appending it to global_post_processors list'
            )
            meta = MetaProcessor(
                'meta',
                record_name='octodns-meta',
                include_time=False,
                include_provider=True,
            )
            self.processors[meta.id] = meta
            self.global_post_processors.append(meta.id)

        plan_outputs_config: dict[str, Any] = manager_config.get(
            'plan_outputs'
        ) or {
            '_logger': {
                'class': 'octodns.provider.plan.PlanLogger',
                'level': 'info',
            }
        }
        self.plan_outputs: dict[str, PlanOutput] = self._config_plan_outputs(
            plan_outputs_config
        )

    def _config_zones(self, zones: dict[str, Any]) -> IdnaDict[str, Any]:
        # record the set of configured zones we have as they are
        configured_zones: set[str] = set([z.lower() for z in zones.keys()])
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

    def _config_executor(
        self, manager_config: dict[str, Any], max_workers: Optional[int] = None
    ) -> ThreadPoolExecutor | MainThreadExecutor:
        max_workers = (
            manager_config.get('max_workers') or 1
            if max_workers is None
            else max_workers
        )
        self.log.info('_config_executor: max_workers=%d', max_workers)
        if max_workers > 1:
            return ThreadPoolExecutor(max_workers=max_workers)
        return MainThreadExecutor()

    def _config_include_meta(
        self, manager_config: dict[str, Any], include_meta: bool = False
    ) -> bool:
        include_meta = include_meta or manager_config.get('include_meta', False)
        self.log.info('_config_include_meta: include_meta=%s', include_meta)
        return include_meta

    def _config_enable_checksum(
        self, manager_config: dict[str, Any], enable_checksum: bool = False
    ) -> bool:
        enable_checksum = enable_checksum or manager_config.get(
            'enable_checksum', False
        )
        self.log.info(
            '_config_enable_checksum: enable_checksum=%s', enable_checksum
        )
        return enable_checksum

    def _config_auto_arpa(
        self, manager_config: dict[str, Any], auto_arpa: bool = False
    ) -> bool | dict[str, Any]:
        auto_arpa = auto_arpa or manager_config.get('auto_arpa', False)
        self.log.info('_config_auto_arpa: auto_arpa=%s', auto_arpa)
        return auto_arpa

    def _config_secret_handlers(
        self, secret_handlers_config: dict[str, Any]
    ) -> dict[str, Any]:
        self.log.debug('_config_secret_handlers: configuring secret_handlers')
        secret_handlers: dict[str, Any] = {}
        for sh_name, sh_config in secret_handlers_config.items():
            # Get our class and remove it from the secret handler config
            try:
                _class = sh_config.pop('class')  # type: ignore[call-overload]
            except KeyError:
                self.log.exception('Invalid secret handler class')
                raise ManagerException(
                    f'Secret Handler {sh_name} is missing class, {sh_config.context}'  # type: ignore[attr-defined]
                )
            _class, module, version = self._get_named_class(
                'secret handler', _class, sh_config.context  # type: ignore[attr-defined]
            )
            kwargs: dict[str, Any] = self._build_kwargs(sh_config)
            try:
                secret_handlers[sh_name] = _class(sh_name, **kwargs)
                self.log.info(
                    '__init__: secret_handler=%s (%s %s)',
                    sh_name,
                    module,
                    version,
                )
            except TypeError:
                self.log.exception('Invalid secret handler config')
                raise ManagerException(
                    f'Incorrect secret handler config for {sh_name}, {sh_config.context}'  # type: ignore[attr-defined]
                )

        return secret_handlers

    def _config_providers(
        self, providers_config: dict[str, Any]
    ) -> dict[str, BaseProvider]:
        self.log.debug('_config_providers: configuring providers')
        providers: dict[str, BaseProvider] = {}
        for provider_name, provider_config in providers_config.items():
            # Get our class and remove it from the provider_config
            try:
                _class = provider_config.pop('class')  # type: ignore[call-overload]
            except KeyError:
                self.log.exception('Invalid provider class')
                raise ManagerException(
                    f'Provider {provider_name} is missing class, {provider_config.context}'  # type: ignore[attr-defined]
                )
            _class, module, version = self._get_named_class(
                'provider', _class, provider_config.context  # type: ignore[attr-defined]
            )
            kwargs: dict[str, Any] = self._build_kwargs(provider_config)
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
                    f'Incorrect provider config for {provider_name}, {provider_config.context}'  # type: ignore[attr-defined]
                )

        return providers

    def _config_processors(
        self, processors_config: dict[str, Any]
    ) -> dict[str, Any]:
        processors: dict[str, Any] = {}
        for processor_name, processor_config in processors_config.items():
            try:
                _class = processor_config.pop('class')  # type: ignore[call-overload]
            except KeyError:
                self.log.exception('Invalid processor class')
                raise ManagerException(
                    f'Processor {processor_name} is missing class, {processor_config.context}'  # type: ignore[attr-defined]
                )
            _class, module, version = self._get_named_class(
                'processor', _class, processor_config.context  # type: ignore[attr-defined]
            )
            kwargs: dict[str, Any] = self._build_kwargs(processor_config)
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
                    f'Incorrect processor config for {processor_name}, {processor_config.context}'  # type: ignore[attr-defined]
                )
        return processors

    def _config_validators(self, validators_config: dict[str, Any]) -> None:
        # Parses the top-level `validators:` config section, instantiates each
        # validator, and registers it into the available registry via
        # Record.register_validator. _configure_validators then decides which
        # to activate based on manager.enabled and manager.validators.
        for validator_name, validator_config in validators_config.items():
            context = getattr(validator_config, 'context', '')  # type: ignore[attr-defined]
            try:
                _class = validator_config.pop('class')  # type: ignore[call-overload]
            except KeyError:
                self.log.exception('Invalid validator class')
                raise ManagerException(
                    f'Validator {validator_name} is missing class, {context}'
                )
            _class, module, version = self._get_named_class(
                'validator', _class, context
            )
            types: Optional[list[str]] = validator_config.pop('types', None)
            if isinstance(types, str):
                types = [types]
            kwargs: dict[str, Any] = self._build_kwargs(validator_config)
            try:
                instance = _class(validator_name, **kwargs)
            except TypeError:
                self.log.exception('Invalid validator config')
                raise ManagerException(
                    f'Incorrect validator config for {validator_name}, {context}'
                )
            if isinstance(instance, (RecordValidator, ValueValidator)):
                try:
                    Record.register_validator(instance, types=types)
                except RecordException as e:
                    raise ManagerException(str(e)) from e
            elif isinstance(instance, ZoneValidator):
                try:
                    Zone.register_zone_validator(instance)
                except ZoneException as e:
                    raise ManagerException(str(e)) from e
            else:
                raise ManagerException(
                    f'Validator {validator_name} ({_class.__name__}) must extend RecordValidator, ValueValidator, or ZoneValidator'
                )
            self.log.info(
                '__init__: validator=%s (%s %s)',
                validator_name,
                module,
                version,
            )

    def _configure_validators(self, manager_config: dict[str, Any]) -> None:
        validators_config: dict[str, Any] = (
            manager_config.get('validators') or {}
        )

        enabled: tuple[str, ...] | list[str] = validators_config.get(
            'enabled', ('legacy',)
        )
        if isinstance(enabled, str):
            raise ManagerException(
                'manager.validators.enabled must be a list of set names, not a string; '
                f'use [{enabled!r}] to enable a single set'
            )
        self.log.info('_configure_validators: enabling sets %s', list(enabled))
        Record.enable_validators(enabled)  # type: ignore[arg-type]
        Zone.enable_zone_validators(enabled)

        # manager.validators.record.validators is canonical;
        # manager.validators.validators is the deprecated fallback.
        record_config: dict[str, Any] = validators_config.get('record') or {}
        has_new: bool = 'validators' in record_config
        has_old: bool = 'validators' in validators_config
        if has_new and has_old:
            raise ManagerException(
                'manager.validators.record.validators and '
                'manager.validators.validators cannot both be set; '
                'remove manager.validators.validators (deprecated)'
            )
        if has_old:
            deprecated(
                'manager.validators.validators is deprecated, use '
                'manager.validators.record.validators instead. Will be removed in 2.0',
                stacklevel=4,
            )
        add_config: dict[str, Any] = record_config.get(
            'validators', validators_config.get('validators') or {}
        )
        add_key: str = (
            'validators.record.validators'
            if has_new
            else 'validators.validators'
        )
        for record_type, names in add_config.items():
            types: Optional[list[str]] = (
                None if record_type == '*' else [record_type]
            )
            for name in names:
                try:
                    Record.enable_validator(name, types=types)
                except RecordException:
                    raise ManagerException(
                        f'Unknown validator "{name}" in manager.{add_key}["{record_type}"]'
                    )
                self.log.info(
                    '_configure_validators: enabled validator "%s" for "%s"',
                    name,
                    record_type,
                )

        # manager.validators.record.disable_validators is canonical;
        # manager.validators.disable_validators is the deprecated fallback.
        has_new_dis: bool = 'disable_validators' in record_config
        has_old_dis: bool = 'disable_validators' in validators_config
        if has_new_dis and has_old_dis:
            raise ManagerException(
                'manager.validators.record.disable_validators and '
                'manager.validators.disable_validators cannot both be set; '
                'remove manager.validators.disable_validators (deprecated)'
            )
        if has_old_dis:
            deprecated(
                'manager.validators.disable_validators is deprecated, use '
                'manager.validators.record.disable_validators instead. Will be removed in 2.0',
                stacklevel=4,
            )
        disable_config: dict[str, Any] = record_config.get(
            'disable_validators',
            validators_config.get('disable_validators') or {},
        )
        for record_type, ids in disable_config.items():
            types: Optional[list[str]] = (
                None if record_type == '*' else [record_type]
            )
            for validator_id in ids:
                try:
                    removed = Record.disable_validator(
                        validator_id, types=types
                    )
                except RecordException as e:
                    raise ManagerException(str(e)) from e
                if removed == 0:
                    self.log.warning(
                        '_configure_validators: no validator with id "%s" '
                        'registered for "%s"',
                        validator_id,
                        record_type,
                    )
                else:
                    self.log.info(
                        '_configure_validators: disabled validator "%s" for "%s"',
                        validator_id,
                        record_type,
                    )

        zone_config: dict[str, Any] = validators_config.get('zone') or {}
        for name in zone_config.get('validators') or []:
            try:
                Zone.enable_zone_validator(name)
            except ZoneException:
                raise ManagerException(
                    f'Unknown zone validator "{name}" in manager.validators.zone.validators'
                )
            self.log.info(
                '_configure_validators: enabled zone validator "%s"', name
            )

        for validator_id in zone_config.get('disable_validators') or []:
            try:
                removed = Zone.disable_zone_validator(validator_id)
            except ZoneException as e:
                raise ManagerException(str(e)) from e
            if not removed:
                self.log.warning(
                    '_configure_validators: no zone validator with id "%s" active',
                    validator_id,
                )
            else:
                self.log.info(
                    '_configure_validators: disabled zone validator "%s"',
                    validator_id,
                )

    def _config_plan_outputs(
        self, plan_outputs_config: dict[str, Any]
    ) -> dict[str, PlanOutput]:
        plan_outputs: dict[str, PlanOutput] = {}
        for plan_output_name, plan_output_config in plan_outputs_config.items():
            context = getattr(  # type: ignore[attr-defined]
                plan_output_config, 'context', ''
            )
            try:
                _class = plan_output_config.pop('class')  # type: ignore[call-overload]
            except KeyError:
                self.log.exception('Invalid plan_output class')
                raise ManagerException(
                    f'plan_output {plan_output_name} is missing class, {context}'
                )
            _class, module, version = self._get_named_class(
                'plan_output', _class, context
            )
            kwargs: dict[str, Any] = self._build_kwargs(plan_output_config)
            try:
                plan_outputs[plan_output_name] = _class(  # type: ignore[assignment]
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
                    f'Incorrect plan_output config for {plan_output_name}, {context}'
                )

        return plan_outputs

    def _try_version(
        self,
        module_name: str,
        module: Any = None,
        version: Optional[str] = None,
    ) -> Optional[str]:
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
        # TODO: remove the __VERSION__ fallback eventually?
        return getattr(
            module, '__version__', getattr(module, '__VERSION__', None)
        )

    def _import_module(self, module_name: str) -> tuple[Any, str]:
        current: str = module_name
        _next: str = current.rsplit('.', 1)[0]
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

    def _get_named_class(
        self, _type: str, _class: str, context: Any
    ) -> tuple[Any, str, str]:
        try:
            module_name, class_name = _class.rsplit('.', 1)
            module, version = self._import_module(module_name)
        except (ImportError, ValueError):
            self.log.exception(
                '_get_{}_class: Unable to import module %s', _class
            )
            raise ManagerException(
                f'Unknown {_type} class: {_class}, {context}'
            )

        try:
            return getattr(module, class_name), module_name, version
        except AttributeError:
            self.log.exception(
                '_get_named_class: Unable to get class %s from module %s',
                class_name,
                module,
            )
            raise ManagerException(
                f'Unknown {_type} class: {_class}, {context}'
            )

    def _build_kwargs(self, source: dict[str, Any]) -> dict[str, Any]:
        # Build up the arguments we need to pass to the provider
        kwargs: dict[str, Any] = {}
        for k, v in source.items():
            if isinstance(v, dict):
                v = self._build_kwargs(v)
            elif isinstance(v, str):
                if '/' in v:
                    handler, name = v.split('/', 1)
                    try:
                        handler = self.secret_handlers[handler]
                    except KeyError:
                        # we don't have a matching handler, but don't want to
                        # make that an error b/c config values will often
                        # contain /. We don't want to print the values in case
                        # they're sensitive so just provide the key, and even
                        # that only at debug level.
                        self.log.debug(
                            '_build_kwargs: failed to find handler for key "%s"',
                            k,
                        )
                    else:
                        v = handler.fetch(name, source)  # type: ignore[attr-defined]

            kwargs[k] = v

        return kwargs

    def configured_sub_zones(self, zone_name: str) -> set[str]:
        '''
        Accepts either UTF-8 or IDNA encoded zone name and returns the list of
        any configured sub-zones in IDNA form. E.g. for the following

        Configured zones:
          - some.com.
          - other.some.com.
          - deep.thing.some.com.

        It would return
          - other
          - deep.thing

        '''
        if self._configured_sub_zones is None:
            # First time through we compute all the sub-zones

            configured_sub_zones = IdnaDict[str, set[str]]()

            # Get a list of all of our zone names. Sort them from shortest to
            # longest so that parents will always come before their subzones
            zones = sorted(
                self.config['zones'].keys(),
                key=lambda z: len(z),  # type: ignore[arg-type]
                reverse=True,
            )
            zones = deque(zones)
            # Until we're done processing zones
            while zones:
                # Grab the one we'lre going to work on now
                zone = zones.pop()
                dotted = f'.{zone}'
                trimmer = len(dotted)
                subs: set[str] = set()
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
        zone_name: str,
        processors: list[Any],
        sources: list[BaseProvider],
        targets: list[BaseProvider],
        desired: Optional[Zone] = None,
        lenient: bool = False,
    ) -> tuple[list[tuple[BaseProvider, Plan]], Zone]:
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
                    source.populate(zone, lenient=lenient)  # type: ignore[arg-type]
                except TypeError as e:
                    if "unexpected keyword argument 'lenient'" not in str(e):
                        raise
                    deprecated(
                        f'`populate` method does not support the `lenient` param, fallback is DEPRECATED. Will be removed in 2.0. Class {source.__class__.__name__}',
                        stacklevel=99,
                    )
                    self.log.warning(
                        'provider %s does not accept lenient param',
                        source.__class__.__name__,
                    )
                    source.populate(zone)

        for processor in processors:
            try:
                zone = processor.process_source_zone(  # type: ignore[union-attr]
                    zone, sources=sources, lenient=lenient
                )
            except TypeError as e:
                if "unexpected keyword argument 'lenient'" not in str(e):
                    raise
                deprecated(
                    f'`process_source_zone` method does not support the `lenient` param, fallback is DEPRECATED. Will be removed in 2.0. Class {processor.__class__.__name__}',
                    stacklevel=99,
                )
                self.log.warning(
                    'processor %s does not accept lenient param',
                    processor.__class__.__name__,
                )
                zone = processor.process_source_zone(  # type: ignore[union-attr]
                    zone, sources=sources
                )

        zone.validate(lenient=lenient)

        self.log.debug('sync:   planning, zone=%s', zone.decoded_name)
        plans: list[tuple[BaseProvider, Plan]] = []

        for target in targets:
            try:
                plan = target.plan(  # type: ignore[union-attr]
                    zone, processors=processors, lenient=lenient
                )
            except TypeError as e:
                e_str = str(e)
                if "keyword argument 'lenient'" in e_str:
                    deprecated(
                        f'`plan` method does not support the `lenient` param, fallback is DEPRECATED. Will be removed in 2.0. Class {target.__class__.__name__}',
                        stacklevel=99,
                    )
                    self.log.warning(
                        'provider.plan %s does not accept lenient param',
                        target.__class__.__name__,
                    )
                    try:
                        plan = target.plan(zone, processors=processors)  # type: ignore[union-attr]
                    except TypeError as e2:
                        if "keyword argument 'processors'" not in str(e2):
                            raise
                        deprecated(
                            f'`plan` method does not support the `processors` param, fallback is DEPRECATED. Will be removed in 2.0. Class {target.__class__.__name__}',
                            stacklevel=99,
                        )
                        self.log.warning(
                            'provider.plan %s does not accept processors param',
                            target.__class__.__name__,
                        )
                        plan = target.plan(zone)  # type: ignore[union-attr]
                elif "keyword argument 'processors'" in e_str:
                    deprecated(
                        f'`plan` method does not support the `processors` param, fallback is DEPRECATED. Will be removed in 2.0. Class {target.__class__.__name__}',
                        stacklevel=99,
                    )
                    self.log.warning(
                        'provider.plan %s does not accept processors param',
                        target.__class__.__name__,
                    )
                    plan = target.plan(zone)  # type: ignore[union-attr]
                else:
                    raise

            for processor in processors:
                try:
                    plan = processor.process_plan(  # type: ignore[union-attr]
                        plan, sources=sources, target=target, lenient=lenient
                    )
                except TypeError as e:
                    if "unexpected keyword argument 'lenient'" not in str(e):
                        raise
                    deprecated(
                        f'`process_plan` method does not support the `lenient` param, fallback is DEPRECATED. Will be removed in 2.0. Class {processor.__class__.__name__}',
                        stacklevel=99,
                    )
                    self.log.warning(
                        'processor %s does not accept lenient param',
                        processor.__class__.__name__,
                    )
                    plan = processor.process_plan(  # type: ignore[union-attr]
                        plan, sources=sources, target=target
                    )
            if plan:
                plans.append((target, plan))

        # Return the zone as it's the desired state
        return plans, zone

    def _get_sources(
        self,
        decoded_zone_name: str,
        config: dict[str, Any],
        eligible_sources: Optional[Iterable[str]] = None,
    ) -> list[BaseProvider]:
        try:
            sources = config['sources'] or []
        except KeyError:
            raise ManagerException(
                f'Zone {decoded_zone_name} is missing sources'
            )

        if eligible_sources and not [
            s for s in sources if s in eligible_sources
        ]:
            return []

        self.log.info('_get_sources:     sources=%s', sources)

        try:
            # rather than using a list comprehension, we break this loop
            # out so that the `except` block below can reference the
            # `source`
            collected: list[BaseProvider] = []
            for source in sources:
                collected.append(self.providers[source])
            sources = collected
        except KeyError:
            raise ManagerException(
                f'Zone {decoded_zone_name}, unknown source: {source}'  # type: ignore[reportPossiblyUnboundVariable]
            )

        return sources

    def _get_processors(
        self, decoded_zone_name: str, config: dict[str, Any]
    ) -> list[Any]:
        # Build list of processor names
        processors: list[str] = (
            self.global_processors
            + (config.get('processors') or [])
            + self.global_post_processors
        )

        # Translate processor names to processor objects
        try:
            collected: list[Any] = []
            for processor in processors:
                collected.append(self.processors[processor])
            processors = collected
        except KeyError:
            raise ManagerException(
                f'Zone {decoded_zone_name}, unknown processor: {processor}'  # type: ignore[reportPossiblyUnboundVariable]
            )

        return processors

    def _preprocess_zones(
        self,
        zones: dict[str, Any],
        eligible_sources: Optional[Iterable[str]] = None,
        sources: Optional[list[BaseProvider]] = None,
    ) -> dict[str, Any]:
        '''
        This may modify the passed in zone object, it should be ignored after
        the call and the zones returned from this function should be used
        instead.
        '''

        source_zones: dict[str, set[str]] = {}

        # list since we'll be modifying zones in the loop
        for name, config in list(zones.items()):
            if name[0] != '*':
                # this isn't a dynamic zone config, move along
                continue

            # it's dynamic, get a list of zone names from the configured sources
            found_sources = sources or self._get_sources(
                name, config, eligible_sources
            )
            self.log.info(
                '_preprocess_zones: dynamic zone=%s, sources=%s',
                name,
                [s.id for s in found_sources],
            )
            candidates: set[str] = set()
            for source in found_sources:
                if source.id not in source_zones:
                    if not hasattr(source, 'list_zones'):
                        raise ManagerException(
                            f'dynamic zone={name} includes a source, {source.id}, that does not support `list_zones`'
                        )
                    # get this source's zones
                    listed_zones: set[str] = set(source.list_zones())
                    # cache them
                    source_zones[source.id] = listed_zones
                    self.log.debug(
                        '_preprocess_zones: source=%s, list_zones=%s',
                        source.id,
                        listed_zones,
                    )
                # add this source's zones to the candidates
                candidates |= source_zones[source.id]

            self.log.debug(
                '_preprocess_zones: name=%s, candidates=%s', name, candidates
            )

            # remove any zones that are already configured, either explicitly or
            # from a previous dynamic config
            candidates -= set(zones.keys())

            glob: Optional[str] = config.pop('glob', None)
            if glob is not None:
                self.log.debug(
                    '_preprocess_zones: name=%s, glob=%s', name, glob
                )
                candidates = set(fnmatch_filter(candidates, glob))
            else:
                regex: Optional[str] = config.pop('regex', None)
                if regex is not None:
                    self.log.debug(
                        '_preprocess_zones: name=%s, regex=%s', name, regex
                    )
                    compiled_regex: Pattern = re_compile(regex)
                    self.log.debug(
                        '_preprocess_zones: name=%s, compiled=%s',
                        name,
                        compiled_regex,
                    )
                    candidates = set(
                        z for z in candidates if compiled_regex.search(z)
                    )
                else:
                    # old-style wildcard that uses everything
                    self.log.debug(
                        '_preprocess_zones: name=%s, old semantics, catch all',
                        name,
                    )

            self.log.debug(
                '_preprocess_zones: name=%s, matches=%s', name, candidates
            )

            for match in candidates:
                zones[match] = config

            # remove the dynamic config element so we don't try and populate it
            del zones[name]

        return zones

    def sync(
        self,
        eligible_zones: Iterable[str] = [],
        eligible_sources: Iterable[str] = [],
        eligible_targets: Iterable[str] = [],
        dry_run: bool = True,
        force: bool = False,
        plan_output_fh: Optional[Any] = None,
        checksum: Optional[str] = None,
    ) -> int:
        self.log.info(
            'sync: eligible_zones=%s, eligible_targets=%s, dry_run=%s, force=%s, plan_output_fh=%s, checksum=%s',
            eligible_zones,
            eligible_targets,
            dry_run,
            force,
            (
                getattr(
                    plan_output_fh, 'name', plan_output_fh.__class__.__name__
                )
                if plan_output_fh is not None
                else 'stdout'
            ),
            checksum,
        )

        zones = self.config['zones']

        zones = self._preprocess_zones(zones, eligible_sources)

        if eligible_zones:
            zones = IdnaDict[str, Any](
                {n: zones.get(n) for n in eligible_zones}
            )

        includes_arpa: bool = any(e.endswith('arpa.') for e in zones.keys())
        if self.auto_arpa and includes_arpa:
            # it's not safe to mess with auto_arpa when we don't have a complete
            # picture of records, so if any filtering is happening while arpa
            # zones are in play we need to abort
            if any(e.endswith('arpa.') for e in eligible_zones):
                raise ManagerException(
                    'ARPA zones cannot be synced during partial runs when auto_arpa is enabled'
                )
            if eligible_sources:
                raise ManagerException(
                    'eligible_sources is incompatible with auto_arpa'
                )
            if eligible_targets:
                raise ManagerException(
                    'eligible_targets is incompatible with auto_arpa'
                )

        aliased_zones: dict[str, str] = {}
        delayed_arpa: list[dict[str, Any]] = []
        futures: list[MakeThreadFuture] = []

        for zone_name, config in zones.items():
            if config is None:
                raise ManagerException(
                    f'Requested zone "{zone_name}" not found in config'
                )
            decoded_zone_name: str = idna_decode(zone_name)
            self.log.info('sync:   zone=%s', decoded_zone_name)
            if 'alias' in config:
                source_zone: str = config['alias']

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

            lenient: bool = config.get('lenient', False)

            sources: list[BaseProvider] = self._get_sources(
                decoded_zone_name, config, eligible_sources
            )

            try:
                targets = config['targets'] or []
            except KeyError:
                raise ManagerException(
                    f'Zone {decoded_zone_name} is missing targets'
                )

            processors: list[Any] = self._get_processors(
                decoded_zone_name, config
            )
            self.log.info('sync:     processors=%s', [p.id for p in processors])

            if not sources:
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

            self.log.info('sync:     targets=%s', targets)

            try:
                trgs: list[BaseProvider] = []
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
                    f'Zone {decoded_zone_name}, unknown target: {target}'  # type: ignore[reportPossiblyUnboundVariable]
                )

            kwargs: dict[str, Any] = {
                'zone_name': zone_name,
                'processors': processors,
                'sources': sources,
                'targets': targets,
                'lenient': lenient,
            }

            if self.auto_arpa and zone_name.endswith('arpa.'):
                delayed_arpa.append(kwargs)
            else:
                futures.append(
                    self._executor.submit(self._populate_and_plan, **kwargs)
                )

        # Wait on all results and unpack/flatten the plans and store the
        # desired states in case we need them below
        plans: list[tuple[BaseProvider, Plan]] = []
        desired: dict[str, Zone] = {}
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
        plans += [p for f in futures for p in f.result()[0]]  # type: ignore[misc]

        if delayed_arpa:
            # if delaying arpa all of the non-arpa zones have been processed now
            # so it's time to plan them
            self.log.info(
                'sync: processing %d delayed arpa zones', len(delayed_arpa)
            )
            # populate and plan them
            futures = [
                self._executor.submit(self._populate_and_plan, **kwargs)
                for kwargs in delayed_arpa
            ]
            # wait on the results and unpack/flatten the plans
            plans += [p for f in futures for p in f.result()[0]]  # type: ignore[misc]

        # Best effort sort plans children first so that we create/update
        # children zones before parents which should allow us to more safely
        # extract things into sub-zones. Combining a child back into a parent
        # can't really be done all that safely in general so we'll optimize for
        # this direction.
        plans.sort(key=self._plan_keyer, reverse=True)

        for output in self.plan_outputs.values():
            output.run(  # type: ignore[union-attr]
                plans=plans, log=self.plan_log, fh=plan_output_fh
            )

        computed_checksum: Optional[str] = None
        if plans and self.enable_checksum:
            data = [p[1].data for p in plans]
            data = dumps(data)
            csum = sha256()
            csum.update(data.encode('utf-8'))
            computed_checksum = csum.hexdigest()
            checksum_log = getLogger('Checksum')
            checksum_log.setLevel(INFO)
            checksum_log.info('checksum=%s', computed_checksum)

        if not force:
            self.log.debug('sync:   checking safety')
            for target, plan in plans:
                plan.raise_if_unsafe()

        if dry_run and not checksum:
            return 0
        elif computed_checksum is not None and computed_checksum != checksum:
            raise ManagerException(
                f'checksum={checksum} does not match computed={computed_checksum}'
            )

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

    def compare(self, a: list[str], b: list[str], zone: str) -> list[Any]:
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
            source.populate(za)  # type: ignore[arg-type]
        za.validate()

        zb = self.get_zone(zone)
        for source in b:
            source.populate(zb)  # type: ignore[arg-type]
        zb.validate()

        return zb.changes(za, _AggregateTarget(a + b))  # type: ignore[arg-type]

    def dump(
        self,
        zone: str,
        output_dir: str,
        sources: list[str],
        lenient: bool = False,
        split: bool = False,
        output_provider: Optional[str] = None,
    ) -> None:
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

        target: Any
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
            if target.directory != output_dir:  # type: ignore[attr-defined]
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
                target = target.copy()  # type: ignore[attr-defined]
                self.log.info(
                    'dump: setting directory of output_provider copy to %s',
                    output_dir,
                )
                target.directory = output_dir  # type: ignore[attr-defined]
        else:
            self.log.info('dump: using custom YamlProvider')
            clz = YamlProvider
            if split:
                clz = SplitYamlProvider
            target = clz('dump', output_dir)

        zones = self.config['zones']
        zones = self._preprocess_zones(zones, sources=sources)

        if '*' in zone:
            # we want to do everything
            zones = list(zones.items())
        else:
            # we want to do a specific zone
            try:
                zones = [(zone, zones[zone])]
            except KeyError:
                raise ManagerException(
                    f'Requested zone "{zone}" not found in config'
                )

        for zone_name, config in zones:
            decoded_zone_name = idna_decode(zone_name)
            self.log.info('dump:   zone=%s', decoded_zone_name)

            processors = self._get_processors(
                decoded_zone_name, config  # type: ignore[arg-type]
            )
            self.log.info('dump:     processors=%s', [p.id for p in processors])

            zone_obj = self.get_zone(zone_name)
            for source in sources:
                source.populate(zone_obj, lenient=lenient)  # type: ignore[arg-type]

            # Apply processors
            for processor in processors:
                try:
                    zone_obj = processor.process_source_zone(  # type: ignore[assignment]
                        zone_obj, sources=sources, lenient=lenient
                    )
                except TypeError as e:
                    if "unexpected keyword argument 'lenient'" not in str(e):
                        raise
                    deprecated(
                        f'`process_source_zone` method does not support the `lenient` param, fallback is DEPRECATED. Will be removed in 2.0. Class {processor.__class__.__name__}',
                        stacklevel=99,
                    )
                    self.log.warning(
                        'processor %s does not accept lenient param',
                        processor.__class__.__name__,
                    )
                    zone_obj = processor.process_source_zone(  # type: ignore[assignment]
                        zone_obj, sources=sources
                    )

            zone_obj.validate(lenient=lenient)

            plan = target.plan(zone_obj)  # type: ignore[union-attr]
            if plan is None:
                plan = Plan(zone_obj, zone_obj, [], False)
            target.apply(plan)  # type: ignore[union-attr]

    def validate_configs(self, lenient: bool = False) -> None:
        # TODO: this code can probably be shared with stuff in sync

        zones = self.config['zones']
        zones = self._preprocess_zones(zones)

        for zone_name, config in zones.items():
            decoded_zone_name = idna_decode(zone_name)
            zone_obj = self.get_zone(zone_name)

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
                collected: list[BaseProvider] = []
                for source in sources:
                    collected.append(self.providers[source])
                sources = collected
            except KeyError:
                raise ManagerException(
                    f'Zone {decoded_zone_name}, unknown source: ' + source  # type: ignore[reportPossiblyUnboundVariable]
                )

            lenient = lenient or config.get('lenient', False)
            for source in sources:
                if isinstance(source, YamlProvider):
                    source.populate(zone_obj, lenient=lenient)  # type: ignore[arg-type]

            zone_obj.validate(lenient=lenient)

            # check that processors are in order if any are specified
            processors = config.get('processors') or []
            try:
                # same as above, but for processors this time
                for processor in processors:
                    collected.append(self.processors[processor])
            except KeyError:
                raise ManagerException(
                    f'Zone {decoded_zone_name}, unknown '
                    f'processor: {processor}'  # type: ignore[reportPossiblyUnboundVariable]
                )

    def get_zone(self, zone_name: str) -> Zone:
        if not zone_name[-1] == '.':
            raise ManagerException(
                f'Invalid zone name {idna_decode(zone_name)}, missing ending dot'
            )

        zone = self.config['zones'].get(zone_name)
        if zone is not None:
            sub_zones = self.configured_sub_zones(zone_name)
            update_pcent_threshold = zone.get("update_pcent_threshold", None)
            delete_pcent_threshold = zone.get("delete_pcent_threshold", None)
            ignore_subzone_adds: bool = zone.get("ignore_subzone_adds", False)
            context = getattr(zone, 'context', None)  # type: ignore[attr-defined]
            return Zone(
                idna_encode(zone_name),
                sub_zones,
                update_pcent_threshold,
                delete_pcent_threshold,
                ignore_subzone_adds=ignore_subzone_adds,
                context=context,
            )

        raise ManagerException(f'Unknown zone name {idna_decode(zone_name)}')
