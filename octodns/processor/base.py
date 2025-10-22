#
#
#


class ProcessorException(Exception):
    '''
    Exception raised when a processor encounters an error during processing.

    A subclass of this exception can be raised by processors when they
    encounter invalid configurations, unsupported operations, or other
    processing errors.
    '''

    pass


class BaseProcessor(object):
    '''
    Base class for all octoDNS processors.

    Processors provide hooks into the octoDNS sync process to modify zones and
    records at various stages. They can be used to filter, transform, or
    validate DNS records before planning and applying changes.

    Processors are executed in the order they are configured and can modify:

    - **Source zones** (after sources populate, before planning)
    - **Target zones** (after target populates, before planning)
    - **Source and target zones** (just before computing changes)
    - **Plans** (after planning, before applying)

    Subclasses should override one or more of the ``process_*`` methods to
    implement custom processing logic.

    Example usage::

      processors:
        my-processor:
          class: my.custom.processor.MyProcessor
          # processor-specific configuration

      zones:
        example.com.:
          sources:
            - config
          processors:
            - my-processor
          targets:
            - route53

    See Also:
        - :class:`octodns.processor.filter.TypeAllowlistFilter`
        - :class:`octodns.processor.ownership.OwnershipProcessor`
        - :class:`octodns.processor.acme.AcmeMangingProcessor`
    '''

    def __init__(self, name):
        '''
        Initialize the processor.

        :param name: Unique identifier for this processor instance. Used in
                     logging and configuration references.
        :type name: str

        .. note::
           The ``name`` parameter is deprecated and will be removed in
           version 2.0. Use ``id`` instead.
        '''
        # TODO: name is DEPRECATED, remove in 2.0
        self.id = self.name = name

    def process_source_zone(self, desired, sources):
        '''
        Process the desired zone after all sources have populated.

        Called after all sources have completed populate. Provides an
        opportunity for the processor to modify the desired zone that targets
        will receive.

        :param desired: The desired zone state after all sources have populated.
                        This zone will be used as the target state for planning.
        :type desired: octodns.zone.Zone
        :param sources: List of source providers that populated the zone. May be
                        empty for aliased zones.
        :type sources: list[octodns.provider.base.BaseProvider]

        :return: The modified desired zone, typically the same object passed in.
        :rtype: octodns.zone.Zone

        .. important::
           - Will see ``desired`` after any modifications done by
             ``Provider._process_desired_zone`` and processors configured to run
             before this one.
           - May modify ``desired`` directly.
           - Must return ``desired`` which will normally be the ``desired`` param.
           - Must not modify records directly; ``record.copy`` should be called,
             the results of which can be modified, and then ``Zone.add_record``
             may be used with ``replace=True``.
           - May call ``Zone.remove_record`` to remove records from ``desired``.
           - Sources may be empty, as will be the case for aliased zones.
        '''
        return desired

    def process_target_zone(self, existing, target):
        '''
        Process the existing zone after the target has populated.

        Called after a target has completed ``populate``, before changes are
        computed between ``existing`` and ``desired``. This provides an
        opportunity to modify the existing zone state.

        :param existing: The current zone state from the target provider.
        :type existing: octodns.zone.Zone
        :param target: The target provider that populated the existing zone.
        :type target: octodns.provider.base.BaseProvider

        :return: The modified existing zone, typically the same object passed in.
        :rtype: octodns.zone.Zone

        .. important::
           - Will see ``existing`` after any modifications done by processors
             configured to run before this one.
           - May modify ``existing`` directly.
           - Must return ``existing`` which will normally be the ``existing`` param.
           - Must not modify records directly; ``record.copy`` should be called,
             the results of which can be modified, and then ``Zone.add_record``
             may be used with ``replace=True``.
           - May call ``Zone.remove_record`` to remove records from ``existing``.
        '''
        return existing

    def process_source_and_target_zones(self, desired, existing, target):
        '''
        Process both desired and existing zones before computing changes.

        Called just prior to computing changes for the target provider between
        ``desired`` and ``existing``. Provides an opportunity for the processor
        to modify either or both zones that will be used to compute the changes
        and create the initial plan.

        :param desired: The desired zone state after all source processing.
        :type desired: octodns.zone.Zone
        :param existing: The existing zone state after all target processing.
        :type existing: octodns.zone.Zone
        :param target: The target provider for which changes will be computed.
        :type target: octodns.provider.base.BaseProvider

        :return: A tuple of (desired, existing) zones, typically the same
                 objects passed in.
        :rtype: tuple[octodns.zone.Zone, octodns.zone.Zone]

        .. important::
           - Will see ``desired`` after any modifications done by
             ``Provider._process_desired_zone`` and all processors via
             ``Processor.process_source_zone``.
           - Will see ``existing`` after any modifications done by all processors
             via ``Processor.process_target_zone``.
           - Will see both ``desired`` and ``existing`` after any modifications
             done by any processors configured to run before this one via
             ``Processor.process_source_and_target_zones``.
           - May modify ``desired`` directly.
           - Must return ``desired`` which will normally be the ``desired`` param.
           - May modify ``existing`` directly.
           - Must return ``existing`` which will normally be the ``existing``
             param.
           - Must not modify records directly; ``record.copy`` should be called,
             the results of which can be modified, and then ``Zone.add_record``
             may be used with ``replace=True``.
           - May call ``Zone.remove_record`` to remove records from ``desired``.
           - May call ``Zone.remove_record`` to remove records from ``existing``.
        '''
        return desired, existing

    def process_plan(self, plan, sources, target):
        '''
        Process the plan after it has been computed.

        Called after the planning phase has completed. Provides an opportunity
        for the processor to modify the plan, thus changing the actions that
        will be displayed and potentially applied.

        :param plan: The computed plan containing the changes to be applied.
                     May be None if no changes were detected.
        :type plan: octodns.provider.plan.Plan or None
        :param sources: List of source providers for this zone. May be empty
                        for aliased zones.
        :type sources: list[octodns.provider.base.BaseProvider]
        :param target: The target provider for which the plan was created.
        :type target: octodns.provider.base.BaseProvider

        :return: The modified plan, which may be the same object passed in,
                 a newly created Plan, or None if no changes are needed.
        :rtype: octodns.provider.plan.Plan or None

        .. important::
           - ``plan`` may be None if no changes were detected; if so, a ``Plan``
             may still be created and returned.
           - May modify ``plan.changes`` directly or create a new ``Plan``.
           - Does not have to modify ``plan.desired`` and/or ``plan.existing`` to
             line up with any modifications made to ``plan.changes``.
           - Should copy over ``plan.exists``, ``plan.update_pcent_threshold``,
             and ``plan.delete_pcent_threshold`` when creating a new ``Plan``.
           - Must return a ``Plan`` which may be ``plan`` or can be a newly
             created one with ``plan.desired`` and ``plan.existing`` copied over
             as-is or modified.
           - Sources may be empty, as will be the case for aliased zones.
        '''
        # plan may be None if no changes were detected up until now, the
        # process may still create a plan.
        # sources may be empty, as will be the case for aliased zones
        return plan
