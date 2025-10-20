#
#
#

from ..source.base import BaseSource
from ..zone import Zone
from . import SupportsException
from .plan import Plan


class BaseProvider(BaseSource):
    '''
    Base class for all octoDNS providers.

    Providers extend :class:`octodns.source.base.BaseSource` to add the ability
    to apply DNS changes to a target system. While sources only need to
    implement ``populate()`` to read DNS data, providers also implement
    ``plan()`` and ``apply()`` to manage the complete sync workflow.

    The provider workflow:

    1. **Populate**: Load current state from the provider via ``populate()``
    2. **Process**: Modify zones through ``_process_desired_zone()`` and
       ``_process_existing_zone()`` to handle provider-specific limitations
    3. **Plan**: Compute changes between desired and existing state via ``plan()``
    4. **Apply**: Submit approved changes to the provider via ``apply()``

    Subclasses must implement:

    - **_apply(plan)**: Actually submit changes to the provider's API/backend

    Subclasses should override as needed:

    - **_process_desired_zone(desired)**: Modify desired state before planning
    - **_process_existing_zone(existing, desired)**: Modify existing state before planning
    - **_include_change(change)**: Filter out false positive changes
    - **_extra_changes(existing, desired, changes)**: Add provider-specific changes
    - **_plan_meta(existing, desired, changes)**: Add metadata to the plan

    Example provider configuration::

      providers:
        route53:
          class: octodns_route53.Route53Provider
          access_key_id: env/AWS_ACCESS_KEY_ID
          secret_access_key: env/AWS_SECRET_ACCESS_KEY

      zones:
        example.com.:
          sources:
            - config
          targets:
            - route53

    See Also:
        - :class:`octodns.source.base.BaseSource`
        - :class:`octodns.provider.plan.Plan`
        - :class:`octodns.provider.yaml.YamlProvider`
        - :doc:`/zone_lifecycle`
    '''

    def __init__(
        self,
        id,
        apply_disabled=False,
        update_pcent_threshold=Plan.MAX_SAFE_UPDATE_PCENT,
        delete_pcent_threshold=Plan.MAX_SAFE_DELETE_PCENT,
        strict_supports=True,
        root_ns_warnings=True,
    ):
        '''
        Initialize the provider.

        :param id: Unique identifier for this provider instance.
        :type id: str
        :param apply_disabled: If True, the provider will plan changes but not
                               apply them. Useful for read-only/validation mode.
        :type apply_disabled: bool
        :param update_pcent_threshold: Maximum percentage of existing records
                                       that can be updated in one sync before
                                       requiring ``--force``. Default: 0.3 (30%).
        :type update_pcent_threshold: float
        :param delete_pcent_threshold: Maximum percentage of existing records
                                       that can be deleted in one sync before
                                       requiring ``--force``. Default: 0.3 (30%).
        :type delete_pcent_threshold: float
        :param strict_supports: If True, raise exceptions when unsupported
                                features are encountered. If False, log warnings
                                and attempt to work around limitations.
        :type strict_supports: bool
        :param root_ns_warnings: If True, log warnings about root NS record
                                 handling. If False, silently handle root NS.
        :type root_ns_warnings: bool
        '''
        super().__init__(id)
        self.log.debug(
            '__init__: id=%s, apply_disabled=%s, '
            'update_pcent_threshold=%.2f, '
            'delete_pcent_threshold=%.2f, '
            'strict_supports=%s, '
            'root_ns_warnings=%s',
            id,
            apply_disabled,
            update_pcent_threshold,
            delete_pcent_threshold,
            strict_supports,
            root_ns_warnings,
        )
        self.apply_disabled = apply_disabled
        self.update_pcent_threshold = update_pcent_threshold
        self.delete_pcent_threshold = delete_pcent_threshold
        self.strict_supports = strict_supports
        self.root_ns_warnings = root_ns_warnings

    def _process_desired_zone(self, desired):
        '''
        Process the desired zone before planning.

        Called during the planning phase to modify the desired zone records
        before changes are computed. This is where providers handle their
        limitations by removing or modifying records that aren't supported. The
        parent method will deal with "standard" unsupported cases like types,
        dynamic, and root NS handling. The ``desired`` zone is a shallow copy
        (see :meth:`octodns.zone.Zone.copy`).

        :param desired: The desired zone state to be processed. This is a shallow
                        copy that can be modified.
        :type desired: octodns.zone.Zone

        :return: The processed desired zone, typically the same object passed in.
        :rtype: octodns.zone.Zone

        .. important::
           - Must call ``super()`` at an appropriate point, generally as the
             final step of the method, returning the result of the super call.
           - May modify ``desired`` directly.
           - Must not modify records directly; ``record.copy()`` should be called,
             the results of which can be modified, and then ``Zone.add_record()``
             may be used with ``replace=True``.
           - May call ``Zone.remove_record()`` to remove records from ``desired``.
           - Must call :meth:`supports_warn_or_except` with information about any
             changes that are made to have them logged or throw errors depending
             on the provider configuration.
        '''

        for record in desired.records:
            if not self.supports(record):
                msg = f'{record._type} records not supported for {record.fqdn}'
                fallback = 'omitting record'
                self.supports_warn_or_except(msg, fallback)
                desired.remove_record(record)
            elif getattr(record, 'dynamic', False):
                if self.SUPPORTS_DYNAMIC:
                    if not self.SUPPORTS_POOL_VALUE_STATUS:
                        # drop unsupported status flag
                        unsupported_pools = []
                        for _id, pool in record.dynamic.pools.items():
                            for value in pool.data['values']:
                                if value['status'] != 'obey':
                                    unsupported_pools.append(_id)
                        if unsupported_pools:
                            unsupported_pools = ','.join(unsupported_pools)
                            msg = (
                                f'"status" flag used in pools {unsupported_pools}'
                                f' in {record.fqdn} is not supported'
                            )
                            fallback = (
                                'will ignore it and respect the healthcheck'
                            )
                            self.supports_warn_or_except(msg, fallback)
                            record = record.copy()
                            for pool in record.dynamic.pools.values():
                                for value in pool.data['values']:
                                    value['status'] = 'obey'
                            desired.add_record(record, replace=True)

                    if not self.SUPPORTS_DYNAMIC_SUBNETS:
                        subnet_rules = []
                        for i, rule in enumerate(record.dynamic.rules):
                            rule = rule.data
                            if not rule.get('subnets'):
                                continue

                            msg = f'rule {i + 1} contains unsupported subnet matching in {record.fqdn}'
                            if rule.get('geos'):
                                fallback = 'using geos only'
                                self.supports_warn_or_except(msg, fallback)
                            else:
                                fallback = 'skipping the rule'
                                self.supports_warn_or_except(msg, fallback)

                            subnet_rules.append(i)

                        if subnet_rules:
                            record = record.copy()
                            rules = record.dynamic.rules

                            # drop subnet rules in reverse order so indices don't shift during rule deletion
                            for i in sorted(subnet_rules, reverse=True):
                                rule = rules[i].data
                                if rule.get('geos'):
                                    del rule['subnets']
                                else:
                                    del rules[i]

                            # drop any pools rendered unused
                            pools = record.dynamic.pools
                            pools_seen = set()
                            for rule in record.dynamic.rules:
                                pool = rule.data['pool']
                                while pool:
                                    pools_seen.add(pool)
                                    pool = pools[pool].data.get('fallback')
                            pools_unseen = set(pools.keys()) - pools_seen
                            for pool in pools_unseen:
                                self.log.warning(
                                    '%s: skipping pool %s which is rendered unused due to lack of support for subnet targeting',
                                    record.fqdn,
                                    pool,
                                )
                                del pools[pool]

                            desired.add_record(record, replace=True)
                else:
                    msg = f'dynamic records not supported for {record.fqdn}'
                    fallback = 'falling back to simple record'
                    self.supports_warn_or_except(msg, fallback)
                    record = record.copy()
                    record.dynamic = None
                    desired.add_record(record, replace=True)
            elif (
                record._type == 'PTR'
                and len(record.values) > 1
                and not self.SUPPORTS_MULTIVALUE_PTR
            ):
                # replace with a single-value copy
                msg = f'multi-value PTR records not supported for {record.fqdn}'
                fallback = f'falling back to single value, {record.value}'
                self.supports_warn_or_except(msg, fallback)
                record = record.copy()
                record.values = [record.value]
                desired.add_record(record, replace=True)

        record = desired.root_ns
        if self.SUPPORTS_ROOT_NS:
            if not record and self.root_ns_warnings:
                self.log.warning(
                    'root NS record supported, but no record '
                    'is configured for %s',
                    desired.decoded_name,
                )
        else:
            if record:
                # we can't manage root NS records, get rid of it
                msg = f'root NS record not supported for {record.fqdn}'
                fallback = 'ignoring it'
                if self.strict_supports:
                    raise SupportsException(f'{self.id}: {msg}')
                if self.root_ns_warnings:
                    self.log.warning('%s; %s', msg, fallback)
                desired.remove_record(record)

        return desired

    def _process_existing_zone(self, existing, desired):
        '''
        Process the existing zone before planning.

        Called during the planning phase to modify the existing zone records
        before changes are computed. This allows providers to normalize or filter
        the current state from the provider. The ``existing`` zone is a shallow
        copy (see :meth:`octodns.zone.Zone.copy`).

        :param existing: The existing zone state from the provider. This is a
                         shallow copy that can be modified.
        :type existing: octodns.zone.Zone
        :param desired: The desired zone state. This is for reference only and
                        must not be modified.
        :type desired: octodns.zone.Zone

        :return: The processed existing zone, typically the same object passed in.
        :rtype: octodns.zone.Zone

        .. important::
           - ``desired`` must not be modified in any way; it is only for reference.
           - Must call ``super()`` at an appropriate point, generally as the
             final step of the method, returning the result of the super call.
           - May modify ``existing`` directly.
           - Must not modify records directly; ``record.copy()`` should be called,
             the results of which can be modified, and then ``Zone.add_record()``
             may be used with ``replace=True``.
           - May call ``Zone.remove_record()`` to remove records from ``existing``.
           - Must call :meth:`supports_warn_or_except` with information about any
             changes that are made to have them logged or throw errors depending
             on the provider configuration.
        '''

        existing_root_ns = existing.root_ns
        if existing_root_ns and (
            not self.SUPPORTS_ROOT_NS or not desired.root_ns
        ):
            if self.root_ns_warnings:
                self.log.info(
                    'root NS record in existing, but not supported or '
                    'not configured; ignoring it'
                )
            existing.remove_record(existing_root_ns)

        return existing

    def _include_change(self, change):
        '''
        Filter out false positive changes.

        Called during planning to allow providers to filter out changes that
        are false positives due to peculiarities in their implementation (e.g.,
        providers that enforce minimum TTLs).

        :param change: A change being considered for inclusion in the plan.
        :type change: octodns.record.change.Change

        :return: True if the change should be included in the plan, False to
                 filter it out.
        :rtype: bool
        '''
        return True

    def _extra_changes(self, existing, desired, changes):
        '''
        Add provider-specific extra changes to the plan.

        Called during planning to allow providers to add extra changes that are
        necessary to update ancillary record data or configure the zone (e.g.,
        base NS records that must be managed separately).

        :param existing: The existing zone state.
        :type existing: octodns.zone.Zone
        :param desired: The desired zone state.
        :type desired: octodns.zone.Zone
        :param changes: The list of changes already computed.
        :type changes: list[octodns.record.change.Change]

        :return: A list of additional changes to add to the plan. Return an
                 empty list if no extra changes are needed.
        :rtype: list[octodns.record.change.Change]
        '''
        return []

    def _plan_meta(self, existing, desired, changes):
        '''
        Indicate provider-specific metadata changes to the zone.

        Called during planning to allow providers to indicate they have "meta"
        changes to the zone which are unrelated to records. Examples may include
        service plan changes, replication settings, and notes.

        :param existing: The existing zone state.
        :type existing: octodns.zone.Zone
        :param desired: The desired zone state.
        :type desired: octodns.zone.Zone
        :param changes: The list of changes computed for this plan.
        :type changes: list[octodns.record.change.Change]

        :return: Arbitrary metadata about zone-level changes. The only
                 requirement is that ``pprint.pformat`` can display it. A dict
                 is recommended. Return None if no meta changes.
        :rtype: dict or None
        '''
        return None

    def supports_warn_or_except(self, msg, fallback):
        '''
        Handle unsupported features based on strict_supports setting.

        If ``strict_supports`` is True, raises a :class:`SupportsException`.
        Otherwise, logs a warning with the message and fallback behavior.

        :param msg: Description of the unsupported feature or limitation.
        :type msg: str
        :param fallback: Description of the fallback behavior being used.
        :type fallback: str

        :raises SupportsException: If ``strict_supports`` is True.
        '''
        if self.strict_supports:
            raise SupportsException(f'{self.id}: {msg}')
        self.log.warning('%s; %s', msg, fallback)

    def plan(self, desired, processors=[]):
        '''
        Compute a plan of changes needed to sync the desired state to this provider.

        This is the main planning method that orchestrates the entire planning
        workflow. It populates the current state, processes both desired and
        existing zones, runs processors, computes changes, and returns a
        :class:`Plan` object.

        The planning workflow:

        1. Populate existing state from the provider via :meth:`populate`
        2. Process desired zone via :meth:`_process_desired_zone`
        3. Process existing zone via :meth:`_process_existing_zone`
        4. Run target zone processors
        5. Run source and target zone processors
        6. Compute changes between existing and desired
        7. Filter changes via :meth:`_include_change`
        8. Add extra changes via :meth:`_extra_changes`
        9. Add metadata via :meth:`_plan_meta`
        10. Create and return a Plan (or None if no changes)

        :param desired: The desired zone state to sync to this provider.
        :type desired: octodns.zone.Zone
        :param processors: List of processors to run during planning.
        :type processors: list[octodns.processor.base.BaseProcessor]

        :return: A Plan containing the computed changes, or None if no changes
                 are needed.
        :rtype: octodns.provider.plan.Plan or None

        See Also:
            - :doc:`/zone_lifecycle` for details on the complete sync workflow
        '''
        self.log.info('plan: desired=%s', desired.decoded_name)

        existing = Zone(desired.name, desired.sub_zones)
        exists = self.populate(existing, target=True, lenient=True)
        if exists is None:
            # If your code gets this warning see Source.populate for more
            # information
            self.log.warning(
                'Provider %s used in target mode did not return exists', self.id
            )

        # Make a (shallow) copy of the desired state so that everything from
        # now on (in this target) can modify it as they see fit without
        # worrying about impacting other targets.
        desired = desired.copy()

        desired = self._process_desired_zone(desired)

        existing = self._process_existing_zone(existing, desired)

        for processor in processors:
            existing = processor.process_target_zone(existing, target=self)

        for processor in processors:
            desired, existing = processor.process_source_and_target_zones(
                desired, existing, self
            )

        # compute the changes at the zone/record level
        changes = existing.changes(desired, self)

        # allow the provider to filter out false positives
        before = len(changes)
        changes = [c for c in changes if self._include_change(c)]
        after = len(changes)
        if before != after:
            self.log.info('plan:   filtered out %s changes', before - after)

        # allow the provider to add extra changes it needs
        extra = self._extra_changes(
            existing=existing, desired=desired, changes=changes
        )
        if extra:
            self.log.info(
                'plan:   extra changes\n  %s',
                '\n  '.join([str(c) for c in extra]),
            )
            changes += extra

        meta = self._plan_meta(
            existing=existing, desired=desired, changes=changes
        )

        if changes or meta:
            plan = Plan(
                existing,
                desired,
                changes,
                exists,
                update_pcent_threshold=self.update_pcent_threshold,
                delete_pcent_threshold=self.delete_pcent_threshold,
                meta=meta,
            )
            self.log.info('plan:   %s', plan)
            return plan
        self.log.info('plan:   No changes')
        return None

    def apply(self, plan):
        '''
        Apply the planned changes to the provider.

        This is the main apply method that submits the approved plan to the
        provider's backend. If ``apply_disabled`` is True, this method does
        nothing and returns 0.

        :param plan: The plan containing changes to apply.
        :type plan: octodns.provider.plan.Plan

        :return: The number of changes that were applied.
        :rtype: int

        See Also:
            - :meth:`_apply` for the provider-specific implementation
            - :doc:`/zone_lifecycle` for details on the complete sync workflow
        '''
        if self.apply_disabled:
            self.log.info('apply: disabled')
            return 0

        zone_name = plan.desired.decoded_name
        num_changes = len(plan.changes)
        self.log.info('apply: making %d changes to %s', num_changes, zone_name)
        self._apply(plan)
        return len(plan.changes)

    def _apply(self, plan):
        '''
        Actually submit the changes to the provider's backend.

        This is an abstract method that must be implemented by all provider
        subclasses. It should take the changes in the plan and apply them to
        the provider's API or backend system.

        :param plan: The plan containing changes to apply.
        :type plan: octodns.provider.plan.Plan

        :raises NotImplementedError: This base class method must be overridden
                                     by subclasses.

        .. important::
           - Must implement the actual logic to submit changes to the provider.
           - Should handle errors appropriately (log, raise exceptions, etc.).
           - May apply changes in any order that makes sense for the provider
             with as much safety as possible given the API methods available.
             Often the order of changes should apply deletes before adds to
             avoid comflicts during type changes, specidically **CNAME** <->
             other types. If the provider's API supports batching or atomic
             changes they should be used.
           - Should be idempotent where possible.
        '''
        raise NotImplementedError('Abstract base class, _apply method missing')
