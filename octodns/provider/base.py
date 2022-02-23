#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from ..source.base import BaseSource
from ..zone import Zone
from .plan import Plan
from . import SupportsException


class BaseProvider(BaseSource):

    def __init__(self, id, apply_disabled=False,
                 update_pcent_threshold=Plan.MAX_SAFE_UPDATE_PCENT,
                 delete_pcent_threshold=Plan.MAX_SAFE_DELETE_PCENT,
                 strict_supports=False):
        super(BaseProvider, self).__init__(id)
        self.log.debug('__init__: id=%s, apply_disabled=%s, '
                       'update_pcent_threshold=%.2f, '
                       'delete_pcent_threshold=%.2f',
                       id,
                       apply_disabled,
                       update_pcent_threshold,
                       delete_pcent_threshold)
        self.apply_disabled = apply_disabled
        self.update_pcent_threshold = update_pcent_threshold
        self.delete_pcent_threshold = delete_pcent_threshold
        self.strict_supports = strict_supports

    def _process_desired_zone(self, desired):
        '''
        An opportunity for providers to modify the desired zone records before
        planning. `desired` is a "shallow" copy, see `Zone.copy` for more
        information

        - Must call `super` at an appropriate point for their work, generally
          that means as the final step of the method, returning the result of
          the `super` call.
        - May modify `desired` directly.
        - Must not modify records directly, `record.copy` should be called,
          the results of which can be modified, and then `Zone.add_record` may
          be used with `replace=True`.
        - May call `Zone.remove_record` to remove records from `desired`.
        - Must call supports_warn_or_except with information about any changes
          that are made to have them logged or throw errors depending on the
          provider configuration.
        '''

        for record in desired.records:
            if record._type not in self.SUPPORTS:
                msg = f'{record._type} records not supported for {record.fqdn}'
                fallback = 'omitting record'
                self.supports_warn_or_except(msg, fallback)
                desired.remove_record(record)
            elif getattr(record, 'dynamic', False):
                if self.SUPPORTS_DYNAMIC:
                    if self.SUPPORTS_POOL_VALUE_STATUS:
                        continue
                    # drop unsupported up flag
                    unsupported_pools = []
                    for _id, pool in record.dynamic.pools.items():
                        for value in pool.data['values']:
                            if value['status'] != 'obey':
                                unsupported_pools.append(_id)
                    if not unsupported_pools:
                        continue
                    unsupported_pools = ','.join(unsupported_pools)
                    msg = f'"status" flag used in pools {unsupported_pools}' \
                        f' in {record.fqdn} is not supported'
                    fallback = 'will ignore it and respect the healthcheck'
                    self.supports_warn_or_except(msg, fallback)
                    record = record.copy()
                    for pool in record.dynamic.pools.values():
                        for value in pool.data['values']:
                            value['status'] = 'obey'
                    desired.add_record(record, replace=True)
                else:
                    msg = f'dynamic records not supported for {record.fqdn}'
                    fallback = 'falling back to simple record'
                    self.supports_warn_or_except(msg, fallback)
                    record = record.copy()
                    record.dynamic = None
                    desired.add_record(record, replace=True)
            elif record._type == 'PTR' and len(record.values) > 1 and \
                    not self.SUPPORTS_MULTIVALUE_PTR:
                # replace with a single-value copy
                msg = \
                    f'multi-value PTR records not supported for {record.fqdn}'
                fallback = f'falling back to single value, {record.value}'
                self.supports_warn_or_except(msg, fallback)
                record = record.copy()
                record.values = [record.value]
                desired.add_record(record, replace=True)

        record = desired.root_ns
        if self.SUPPORTS_ROOT_NS:
            if not record:
                self.log.warning('root NS record supported, but no record '
                                 'is configured for %s', desired.name)
        else:
            if record:
                # we can't manage root NS records, get rid of it
                msg = \
                    f'root NS record not supported for {record.fqdn}'
                fallback = 'ignoring it'
                self.supports_warn_or_except(msg, fallback)
                desired.remove_record(record)

        return desired

    def _process_existing_zone(self, existing, desired):
        '''
        An opportunity for providers to modify the existing zone records before
        planning. `existing` is a "shallow" copy, see `Zone.copy` for more
        information

        - `desired` must not be modified in anyway, it is only for reference
        - Must call `super` at an appropriate point for their work, generally
          that means as the final step of the method, returning the result of
          the `super` call.
        - May modify `existing` directly.
        - Must not modify records directly, `record.copy` should be called,
          the results of which can be modified, and then `Zone.add_record` may
          be used with `replace=True`.
        - May call `Zone.remove_record` to remove records from `existing`.
        - Must call supports_warn_or_except with information about any changes
          that are made to have them logged or throw errors depending on the
          provider configuration.
        '''

        existing_root_ns = existing.root_ns
        if existing_root_ns and (not self.SUPPORTS_ROOT_NS or
                                 not desired.root_ns):
            self.log.info('root NS record in existing, but not supported or '
                          'not configured; ignoring it')
            existing.remove_record(existing_root_ns)

        return existing

    def _include_change(self, change):
        '''
        An opportunity for providers to filter out false positives due to
        peculiarities in their implementation. E.g. minimum TTLs.
        '''
        return True

    def _extra_changes(self, existing, desired, changes):
        '''
        An opportunity for providers to add extra changes to the plan that are
        necessary to update ancillary record data or configure the zone. E.g.
        base NS records.
        '''
        return []

    def supports_warn_or_except(self, msg, fallback):
        if self.strict_supports:
            raise SupportsException(f'{self.id}: {msg}')
        self.log.warning('%s; %s', msg, fallback)

    def plan(self, desired, processors=[]):
        self.log.info('plan: desired=%s', desired.name)

        existing = Zone(desired.name, desired.sub_zones)
        exists = self.populate(existing, target=True, lenient=True)
        if exists is None:
            # If your code gets this warning see Source.populate for more
            # information
            self.log.warning('Provider %s used in target mode did not return '
                             'exists', self.id)

        # Make a (shallow) copy of the desired state so that everything from
        # now on (in this target) can modify it as they see fit without
        # worrying about impacting other targets.
        desired = desired.copy()

        desired = self._process_desired_zone(desired)

        existing = self._process_existing_zone(existing, desired)

        for processor in processors:
            existing = processor.process_target_zone(existing, target=self)

        # compute the changes at the zone/record level
        changes = existing.changes(desired, self)

        # allow the provider to filter out false positives
        before = len(changes)
        changes = [c for c in changes if self._include_change(c)]
        after = len(changes)
        if before != after:
            self.log.info('plan:   filtered out %s changes', before - after)

        # allow the provider to add extra changes it needs
        extra = self._extra_changes(existing=existing, desired=desired,
                                    changes=changes)
        if extra:
            self.log.info('plan:   extra changes\n  %s', '\n  '
                          .join([str(c) for c in extra]))
            changes += extra

        if changes:
            plan = Plan(existing, desired, changes, exists,
                        self.update_pcent_threshold,
                        self.delete_pcent_threshold)
            self.log.info('plan:   %s', plan)
            return plan
        self.log.info('plan:   No changes')
        return None

    def apply(self, plan):
        '''
        Submits actual planned changes to the provider. Returns the number of
        changes made
        '''
        if self.apply_disabled:
            self.log.info('apply: disabled')
            return 0

        zone_name = plan.desired.name
        num_changes = len(plan.changes)
        self.log.info('apply: making %d changes to %s', num_changes,
                      zone_name)
        self._apply(plan)
        return len(plan.changes)

    def _apply(self, plan):
        raise NotImplementedError('Abstract base class, _apply method '
                                  'missing')
