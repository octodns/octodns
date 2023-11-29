#
#
#

from datetime import datetime
from logging import getLogger
from uuid import uuid4

from .. import __version__
from ..record import Record
from .base import BaseProcessor

# TODO: remove once we require python >= 3.11
try:  # pragma: no cover
    from datetime import UTC
except ImportError:  # pragma: no cover
    from datetime import timedelta, timezone

    UTC = timezone(timedelta())


def _keys(values):
    return set(v.split('=', 1)[0] for v in values)


class MetaProcessor(BaseProcessor):
    '''
    Add a special metadata record with timestamps, UUIDs, versions, and/or
    provider name. Will only be updated when there are other changes being made.
    A useful tool to aid in debugging and monitoring of DNS infrastructure.

    Timestamps or UUIDs can be useful in checking whether changes are
    propagating, either from a provider's backend to their servers or via AXFRs.

    Provider can be utilized to determine which DNS system responded to a query
    when things are operating in dual authority or split horizon setups.

    Creates a TXT record with the name configured with values based on processor
    settings. Values are in the form `key=<value>`, e.g.
    `time=2023-09-10T05:49:04.246953`

    processors:
      meta:
        class: octodns.processor.meta.MetaProcessor
        # The name to use for the meta record.
        # (default: meta)
        record_name: meta
        # Include a timestamp with a UTC value indicating the timeframe when the
        # last change was made.
        # (default: true)
        include_time: true
        # Include a UUID that can be utilized to uniquely identify the run
        # pushing data
        # (default: false)
        include_uuid: false
        # Include the provider id for the target where data is being pushed
        # (default: false)
        include_provider: false
        # Include the octoDNS version being used
        # (default: false)
        include_version: false
    '''

    @classmethod
    def now(cls):
        return datetime.now(UTC).isoformat()

    @classmethod
    def uuid(cls):
        return str(uuid4())

    def __init__(
        self,
        id,
        record_name='meta',
        include_time=True,
        include_uuid=False,
        include_version=False,
        include_provider=False,
        ttl=60,
    ):
        self.log = getLogger(f'MetaSource[{id}]')
        super().__init__(id)
        self.log.info(
            '__init__: record_name=%s, include_time=%s, include_uuid=%s, include_version=%s, include_provider=%s, ttl=%d',
            record_name,
            include_time,
            include_uuid,
            include_version,
            include_provider,
            ttl,
        )
        self.record_name = record_name
        values = []
        if include_time:
            time = self.now()
            values.append(f'time={time}')
        if include_uuid:
            uuid = self.uuid() if include_uuid else None
            values.append(f'uuid={uuid}')
        if include_version:
            values.append(f'octodns-version={__version__}')
        self.include_provider = include_provider
        values.sort()
        self.values = values
        self.ttl = ttl

    def process_source_zone(self, desired, sources):
        meta = Record.new(
            desired,
            self.record_name,
            {'ttl': self.ttl, 'type': 'TXT', 'values': self.values},
            # we may be passing in empty values here to be filled out later in
            # process_source_and_target_zones
            lenient=True,
        )
        desired.add_record(meta)
        return desired

    def process_source_and_target_zones(self, desired, existing, target):
        if self.include_provider:
            # look for the meta record
            for record in sorted(desired.records):
                if record.name == self.record_name and record._type == 'TXT':
                    # we've found it, make a copy we can modify
                    record = record.copy()
                    record.values = record.values + [f'provider={target.id}']
                    record.values.sort()
                    desired.add_record(record, replace=True)
                    break

        return desired, existing

    def _up_to_date(self, change):
        # existing state, if there is one
        existing = getattr(change, 'existing', None)
        return existing is not None and _keys(existing.values) == _keys(
            self.values
        )

    def process_plan(self, plan, sources, target):
        if (
            plan
            and len(plan.changes) == 1
            and self._up_to_date(plan.changes[0])
        ):
            # the only change is the meta record, and it's not meaningfully
            # changing so we don't actually want to make the change
            return None

        # There's more than one thing changing so meta should update and/or meta
        # is meaningfully changing or being created...
        return plan
