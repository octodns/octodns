#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from ..source.base import BaseSource
from ..zone import Zone
from logging import getLogger


class UnsafePlan(Exception):
    pass


class Plan(object):
    log = getLogger('Plan')

    MAX_SAFE_UPDATE_PCENT = .3
    MAX_SAFE_DELETE_PCENT = .3
    MIN_EXISTING_RECORDS = 10

    def __init__(self, existing, desired, changes):
        self.existing = existing
        self.desired = desired
        self.changes = changes

        change_counts = {
            'Create': 0,
            'Delete': 0,
            'Update': 0
        }
        for change in changes:
            change_counts[change.__class__.__name__] += 1
        self.change_counts = change_counts

        try:
            existing_n = len(self.existing.records)
        except AttributeError:
            existing_n = 0

        self.log.debug('__init__: Creates=%d, Updates=%d, Deletes=%d'
                       'Existing=%d',
                       self.change_counts['Create'],
                       self.change_counts['Update'],
                       self.change_counts['Delete'], existing_n)

    def raise_if_unsafe(self):
        # TODO: what is safe really?
        if self.existing and \
           len(self.existing.records) >= self.MIN_EXISTING_RECORDS:

            existing_record_count = len(self.existing.records)
            update_pcent = self.change_counts['Update'] / existing_record_count
            delete_pcent = self.change_counts['Delete'] / existing_record_count

            if update_pcent > self.MAX_SAFE_UPDATE_PCENT:
                raise UnsafePlan('Too many updates, {} is over {} percent'
                                 '({}/{})'.format(
                                     update_pcent,
                                     self.MAX_SAFE_UPDATE_PCENT * 100,
                                     self.change_counts['Update'],
                                     existing_record_count))
            if delete_pcent > self.MAX_SAFE_DELETE_PCENT:
                raise UnsafePlan('Too many deletes, {} is over {} percent'
                                 '({}/{})'.format(
                                     delete_pcent,
                                     self.MAX_SAFE_DELETE_PCENT * 100,
                                     self.change_counts['Delete'],
                                     existing_record_count))

    def __repr__(self):
        return 'Creates={}, Updates={}, Deletes={}, Existing Records={}' \
            .format(self.change_counts['Create'], self.change_counts['Update'],
                    self.change_counts['Delete'],
                    len(self.existing.records))


class BaseProvider(BaseSource):

    def __init__(self, id, apply_disabled=False):
        super(BaseProvider, self).__init__(id)
        self.log.debug('__init__: id=%s, apply_disabled=%s', id,
                       apply_disabled)
        self.apply_disabled = apply_disabled

    def _include_change(self, change):
        '''
        An opportunity for providers to filter out false positives due to
        pecularities in their implementation. E.g. minimum TTLs.
        '''
        return True

    def _extra_changes(self, existing, changes):
        '''
        An opportunity for providers to add extra changes to the plan that are
        necessary to update ancilary record data or configure the zone. E.g.
        base NS records.
        '''
        return []

    def plan(self, desired):
        self.log.info('plan: desired=%s', desired.name)

        existing = Zone(desired.name, desired.sub_zones)
        self.populate(existing, target=True, lenient=True)

        # compute the changes at the zone/record level
        changes = existing.changes(desired, self)

        # allow the provider to filter out false positives
        before = len(changes)
        changes = filter(self._include_change, changes)
        after = len(changes)
        if before != after:
            self.log.info('plan:   filtered out %s changes', before - after)

        # allow the provider to add extra changes it needs
        extra = self._extra_changes(existing, changes)
        if extra:
            self.log.info('plan:   extra changes\n  %s', '\n  '
                          .join([str(c) for c in extra]))
            changes += extra

        if changes:
            plan = Plan(existing, desired, changes)
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

        self.log.info('apply: making changes')
        self._apply(plan)
        return len(plan.changes)

    def _apply(self, plan):
        raise NotImplementedError('Abstract base class, _apply method '
                                  'missing')
