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
    def get_time(cls):
        return datetime.now(UTC).isoformat()

    @classmethod
    def get_uuid(cls):
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
        self.time = self.get_time() if include_time else None
        self.uuid = self.get_uuid() if include_uuid else None
        self.include_version = include_version
        self.include_provider = include_provider
        self.ttl = ttl

    def values(self, target_id):
        ret = []
        if self.include_version:
            ret.append(f'octodns-version={__version__}')
        if self.include_provider:
            ret.append(f'provider={target_id}')
        if self.time:
            ret.append(f'time={self.time}')
        if self.uuid:
            ret.append(f'uuid={self.uuid}')
        return ret

    def process_source_and_target_zones(self, desired, existing, target):
        meta = Record.new(
            desired,
            self.record_name,
            {'ttl': self.ttl, 'type': 'TXT', 'values': self.values(target.id)},
            # we may be passing in empty values here to be filled out later in
            # process_source_and_target_zones
            lenient=True,
        )
        desired.add_record(meta)
        return desired, existing

    def _is_up_to_date_meta(self, change, target_id):
        # always something so we can see if its type and name
        record = change.record
        # existing state, if there is one
        existing = getattr(change, 'existing', None)
        return (
            record._type == 'TXT'
            and record.name == self.record_name
            and existing is not None
            # don't care about the values here, just the fields/keys
            and _keys(self.values(target_id)) == _keys(existing.values)
        )

    def process_plan(self, plan, sources, target):
        if (
            plan
            and len(plan.changes) == 1
            and self._is_up_to_date_meta(plan.changes[0], target.id)
        ):
            # the only change is the meta record, and it's not meaningfully
            # changing so we don't actually want to make the update, meta should
            # only be enough to cause a plan on its own if the fields changed
            return None

        # There's more than one thing changing so meta should update and/or meta
        # is meaningfully changing or being created...
        return plan
