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
                 manage_root_ns=False,
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
        self.manage_root_ns = manage_root_ns
        self.update_pcent_threshold = update_pcent_threshold
        self.delete_pcent_threshold = delete_pcent_threshold

    def _check_root_ns(self, change):
        '''
        Checks ability for provider root NS support.
        '''

        return not (change.record._type == 'NS' and
                    change.record.name == '' and
                    not (self.SUPPORTS_ROOT_NS and
                         self.manage_root_ns))

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

    def plan(self, desired):
        self.log.info('plan: desired=%s', desired.name)

        existing = Zone(desired.name, desired.sub_zones)
        exists = self.populate(existing, target=True, lenient=True)
        if exists is None:
            # If your code gets this warning see Source.populate for more
            # information
            self.log.warn('Provider %s used in target mode did not return '
                          'exists', self.id)

        # compute the changes at the zone/record level
        changes = existing.changes(desired, self)

        # allow the provider to filter out false positives
        before = len(changes)
        changes = [c for c in changes if self._include_change(c) and
                   self._check_root_ns(c)]
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

        self.log.info('apply: making changes')
        self._apply(plan)
        return len(plan.changes)

    def _apply(self, plan):
        raise NotImplementedError('Abstract base class, _apply method '
                                  'missing')
