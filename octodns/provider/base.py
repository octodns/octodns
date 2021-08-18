#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from six import text_type

from ..source.base import BaseSource
from ..zone import Zone
from .plan import Plan


class BaseProvider(BaseSource):

    def __init__(self, id, apply_disabled=False,
                 update_pcent_threshold=Plan.MAX_SAFE_UPDATE_PCENT,
                 delete_pcent_threshold=Plan.MAX_SAFE_DELETE_PCENT):
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

    def _process_desired_zone(self, desired):
        '''
        Providers can use this method to make any custom changes to the
        desired zone.
        '''
        if self.SUPPORTS_MUTLIVALUE_PTR:
            # nothing do here
            return desired

        new_desired = Zone(desired.name, desired.sub_zones)
        for record in desired.records:
            if record._type == 'PTR' and len(record.values) > 1:
                # replace with a single-value copy
                self.log.warn('does not support multi-value PTR records; '
                              'will use only %s for %s', record.value,
                              record.fqdn)
                record = record.copy()
                record.values = [record.values[0]]

            new_desired.add_record(record)

        return new_desired

    def plan(self, desired, processors=[]):
        self.log.info('plan: desired=%s', desired.name)

        existing = Zone(desired.name, desired.sub_zones)
        exists = self.populate(existing, target=True, lenient=True)
        if exists is None:
            # If your code gets this warning see Source.populate for more
            # information
            self.log.warn('Provider %s used in target mode did not return '
                          'exists', self.id)

        for processor in processors:
            existing = processor.process_target_zone(existing, target=self)

        # process desired zone for any custom zone/record modification
        desired = self._process_desired_zone(desired)

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
