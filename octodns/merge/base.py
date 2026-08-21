#
#
#
#

from logging import getLogger

from ..record.exception import RecordException


class MergerRegistry:
    '''
    Stores and resolves merger instances by id.

    Unlike the processor/validator registries this one is intentionally
    small: it only needs to map an ``id`` to a configured merger instance
    and to hand the manager a single ``merge`` entry point that folds the
    configured mergers over an incoming record.
    '''

    log = getLogger('Merge')

    def __init__(self):
        self.mergers = {}
        self.configured = False

    def __contains__(self, id):
        return id in self.mergers

    def __getitem__(self, id):
        return self.mergers[id]

    def __len__(self):
        return len(self.mergers)

    def __iter__(self):
        return iter(self.mergers)

    def register(self, merger, id=None, replace=False):
        if not isinstance(merger, BaseMerger):
            raise RecordException(
                f'{merger.__class__.__name__} must be a BaseMerger instance'
            )
        if id is None:
            id = merger.id
        if not id:
            raise ValueError(
                f'{merger.__class__.__name__} requires a non-empty id'
            )
        if id in self.mergers and not replace:
            raise RecordException(f'Merger id "{id}" already registered')
        self.mergers[id] = merger

    def enable(self, id):
        if id not in self.mergers:
            raise RecordException(f'Unknown merger id "{id}"')

    def disable(self, id):
        if id not in self.mergers:
            raise RecordException(f'Unknown merger id "{id}"')
        return self.mergers.pop(id)

    def available(self):
        return {
            id: merger.__class__.__name__ for id, merger in self.mergers.items()
        }


# module-level singleton, mirroring the pattern used for VALIDATORS
REGISTRY = MergerRegistry()


class BaseMerger:
    '''
    Base class for mergers.

    A merger is responsible for deciding whether two records with the same
    name and type should be combined, and if so how. It is fully
    delegated every decision — type awareness, TTL handling, value
    combination, logging, and any per-zone opt-in policy (e.g. requiring
    ``octodns.merge:true``) — so the zone enforces none of those.

    Subclasses override ``merge``. It receives the accumulated ``existing``
    record and the incoming ``record`` (both already validated, same name
    and type) and must return the merged ``Record`` or ``None`` if there is
    nothing to merge.
    '''

    id = None
    log = getLogger('Merge')
    # record type this merger handles (e.g. ``'CAA'``). Mergers that only act
    # on one record type should set it so records of other types pass through
    # unchanged when the fold re-supplies them.
    _type = None

    def merge(self, existing, record):
        '''
        Merge ``record`` into ``existing``.

        :param existing: The accumulated record so far (already merged by
                         any earlier mergers in the zone's list).
        :param record: The incoming record currently being added to the
                       zone. Re-supplied unchanged to every merger so a
                       merger only ever *adds* to a merge.
        :return: The merged ``Record``, or ``None`` if there is nothing to
                 merge.
        '''
        return None

    def _merged_record(self, existing, record, values):
        '''
        Build a new record of ``existing``'s class carrying the merged
        ``values`` (a list of value objects).

        The merged record keeps ``existing``'s ``octodns`` metadata (so any
        per-zone opt-in flags survive) and ``existing``'s TTL (so a merge is
        not silently sensitive to record load order). When the incoming record
        carries a different TTL a warning is logged. The source is taken from
        the incoming ``record`` (the record being added).
        '''
        if record.ttl != existing.ttl:
            self.log.warning(
                'merging %s records with differing TTLs (%s vs %s); keeping '
                'existing TTL %s, ignoring incoming %s',
                existing._type,
                existing.ttl,
                record.ttl,
                existing.ttl,
                record.ttl,
            )
        data = {'ttl': existing.ttl, 'type': existing._type, 'values': values}
        if existing.octodns:
            data['octodns'] = existing.octodns
        return existing.__class__(
            existing.zone, existing.name, data, source=record.source
        )
