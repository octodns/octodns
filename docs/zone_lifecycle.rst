Zone Lifecycle During Sync
==========================

This document describes the lifecycle of a :py:class:`~octodns.zone.Zone`
object during the sync process in octoDNS. The
:py:meth:`octodns.manager.Manager.sync` method is the entry point for this
process.

Zone Creation and Population
----------------------------

* **Zone object creation**: :py:class:`~octodns.zone.Zone` objects are created
  by :py:meth:`octodns.manager.Manager.get_zone` with the zone name, configured
  sub-zones, and threshold values from the configuration

* **Source population**: The
  :py:meth:`~octodns.source.base.BaseSource.populate` method is called for each
  source to add records to the zone

  * Sources iterate through their data and call
    :py:meth:`~octodns.zone.Zone.add_record` to add each record

* **Source zone processing**: 

  * :py:meth:`~octodns.processor.base.BaseProcessor.process_source_zone` is
    then called for each configured processor allowing them to modify or filter
    the populated zone

Planning Phase
--------------

* **Plan creation**: Each target provider's
  :py:meth:`~octodns.provider.base.BaseProvider.plan` method is called with the
  final the desired (source) zone

* **Existing zone population**: A new empty :py:class:`~octodns.zone.Zone` is
  created to represent the target's current state

  * The target provider populates this zone via
    :py:meth:`~octodns.source.base.BaseSource.populate` with ``target=True``
    and ``lenient=True``
  * This additonally return whether the zone exists in the target

* **Desired zone copy**: A shallow copy of the desired zone is created via
  :py:meth:`~octodns.zone.Zone.copy`

  * Uses copy-on-write semantics for efficiency
  * Actual record copying is deferred until modifications are needed

* **Desired zone processing**: The target provider calls
  :py:meth:`~octodns.provider.base.BaseProvider._process_desired_zone` to adapt
  records for the target

  * Removes unsupported record types
  * Handles dynamic record support/fallback
  * Handles multi-value PTR record support
  * Handles root NS record support
  * May warn or raise exceptions based on ``strict_supports`` setting
  * Providers may overide this method to add additional checks or
    modifications, they must always call super to allow the above processing

* **Existing zone processing**: The target provider calls
  :py:meth:`~octodns.provider.base.BaseProvider._process_existing_zone` to
  normalize existing records

  * Filters out existing root NS records if not supported or not in desired

* **Target zone processing**: Each processor's
  :py:meth:`~octodns.processor.base.BaseProcessor.process_target_zone` is
  called to modify the existing (target) zone for this provider

  * Processors can filter or modify what octoDNS sees as the current state

* **Source and target zone processing**: Each processor calls
  :py:meth:`~octodns.processor.base.BaseProcessor.process_source_and_target_zones`
  with both zones

  * Allows processors to make coordinated changes to both desired and existing
    states

* **Change detection**: The existing zone's
  :py:meth:`~octodns.zone.Zone.changes` method compares existing records to
  desired records

  * Identifies records to create, update, or delete
  * Honors record-level ``ignored``, ``included``, and ``excluded`` flags
  * Skips records not supported by the target

* **Change filtering**: The target provider's
  :py:meth:`~octodns.provider.base.BaseProvider._include_change` method filters
  false positive changes

  * Providers can exclude changes due to implementation details (e.g., minimum
    TTL enforcement)

* **Extra changes**: The target provider's
  :py:meth:`~octodns.provider.base.BaseProvider._extra_changes` method adds
  provider-specific changes

  * Allows providers to add changes for ancillary records or zone configuration

* **Meta changes**: The target provider's
  :py:meth:`~octodns.provider.base.BaseProvider._plan_meta` method provides
  additional non-record change information

  * Used for zone-level settings or metadata

* **Plan processing**: Each processor calls
  :py:meth:`~octodns.processor.base.BaseProcessor.process_plan` to modify or
  filter the plan

  * Processors can add, modify, or remove changes from the plan

* **Plan finalization**: A :py:class:`~octodns.provider.plan.Plan` object is
  created if changes exist

  * Contains the existing zone, desired zone, list of changes, and metadata
  * Returns ``None`` if no changes are needed

Plan Output and Safety Checks
-----------------------------

* **Plan output**: All configured plan outputs run to display or record the
  plan

  * Default is :py:class:`~octodns.provider.plan.PlanLogger` which logs the
    plan
  * Other outputs include :py:class:`~octodns.provider.plan.PlanJson`,
    :py:class:`~octodns.provider.plan.PlanMarkdown`, and
    :py:class:`~octodns.provider.plan.PlanHtml`

* **Safety validation**: Each plan's
  :py:meth:`~octodns.provider.plan.Plan.raise_if_unsafe` method checks for
  dangerous/numerous changes (unless ``force=True``)

  * Validates update and delete percentages against thresholds
  * Requires force for root NS record changes
  * Raises :py:exc:`~octodns.provider.plan.UnsafePlan` if thresholds exceeded

Apply Phase
-----------

* **Change application**: Each target provider's
  :py:meth:`~octodns.provider.base.BaseProvider.apply` method is called if not
  in dry-run mode

  * Calls the provider's :py:meth:`~octodns.provider.base.BaseProvider._apply`
    method to submit changes
  * The ``_apply`` implementation is provider-specific and interacts with the
    DNS provider's API
  * Returns the number of changes applied

* **Completion**: The sync process completes and returns the total number of
  changes made across all zones and targets
