#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from six import text_type

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
        if self.SUPPORTS_MUTLIVALUE_PTR:
            # nothing do here
            return desired

        for record in desired.records:
            if record._type == 'PTR' and len(record.values) > 1:
                # replace with a single-value copy
                msg = 'multi-value PTR records not supported for {}' \
                    .format(record.fqdn)
                fallback = 'falling back to single value, {}' \
                    .format(record.value)
                self.supports_warn_or_except(msg, fallback)
                record = record.copy(data={
                    'values': [record.value],
                })
                desired.add_record(record, replace=True)

        return desired

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
            raise SupportsException('{}: {}'.format(self.id, msg))
        self.log.warning('{}; {}'.format(msg, fallback))

    def plan(self, desired, processors=[]):
        self.log.info('plan: desired=%s', desired.name)

        # Make a (shallow) copy of the desired state so that everything from
        # now on (in this target) can modify it as they see fit without
        # worrying about impacting other targets.
        desired = desired.copy()

        desired = self._process_desired_zone(desired)

        existing = Zone(desired.name, desired.sub_zones)
        exists = self.populate(existing, target=True, lenient=True)
        if exists is None:
            # If your code gets this warning see Source.populate for more
            # information
            self.log.warn('Provider %s used in target mode did not return '
                          'exists', self.id)

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
                          .join([text_type(c) for c in extra]))
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
