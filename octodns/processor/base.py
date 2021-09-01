#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals


class BaseProcessor(object):

    def __init__(self, name):
        self.name = name

    def process_source_zone(self, desired, sources):
        '''
        Called after all sources have completed populate. Provides an
        opportunity for the processor to modify the desired `Zone` that targets
        will recieve.

        - Will see `desired` after any modifications done by
          `Provider._process_desired_zone` and processors configured to run
          before this one.
        - May modify `desired` directly.
        - Must return `desired` which will normally be the `desired` param.
        - Must not modify records directly, `record.copy` should be called,
          the results of which can be modified, and then `Zone.add_record` may
          be used with `replace=True`.
        - May call `Zone.remove_record` to remove records from `desired`.
        - Sources may be empty, as will be the case for aliased zones.
        '''
        return desired

    def process_target_zone(self, existing, target):
        '''
        Called after a target has completed `populate`, before changes are
        computed between `existing` and `desired`. This provides an opportunity
        to modify the `existing` `Zone`.

        - Will see `existing` after any modifrications done by processors
          configured to run before this one.
        - May modify `existing` directly.
        - Must return `existing` which will normally be the `existing` param.
        - Must not modify records directly, `record.copy` should be called,
          the results of which can be modified, and then `Zone.add_record` may
          be used with `replace=True`.
        - May call `Zone.remove_record` to remove records from `existing`.
        '''
        return existing

    def process_plan(self, plan, sources, target):
        '''
        Called after the planning phase has completed. Provides an opportunity
        for the processors to modify the plan thus changing the actions that
        will be displayed and potentially applied.

        - `plan` may be None if no changes were detected, if so a `Plan` may
          still be created and returned.
        - May modify `plan.changes` directly or create a new `Plan`.
        - Does not have to modify `plan.desired` and/or `plan.existing` to line
          up with any modifications made to `plan.changes`.
        - Should copy over `plan.exists`, `plan.update_pcent_threshold`, and
          `plan.delete_pcent_threshold` when creating a new `Plan`.
        - Must return a `Plan` which may be `plan` or can be a newly created
          one `plan.desired` and `plan.existing` copied over as-is or modified.
        '''
        # plan may be None if no changes were detected up until now, the
        # process may still create a plan.
        # sources may be empty, as will be the case for aliased zones
        return plan
