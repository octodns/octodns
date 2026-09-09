#
#
#
#

from .base import REGISTRY, BaseMerger


class CaaMerger(BaseMerger):
    '''
    Merge CAA records by per-tag value union.

    CAA records carry one or more ``(flags, tag, value)`` triples. This
    merger combines two CAA records that share a name and type by grouping
    their values by ``tag`` and unioning the values within each tag. For
    example merging

    - ``issue=letsencrypt.org`` + ``issuewild=;`` (existing)
    - ``issue=digicert.com`` (incoming)

    yields a single CAA record with ``issue=letsencrypt.org``,
    ``issue=digicert.com``, and ``issuewild=;``.

    Values are matched by ``tag`` only; differing ``flags`` for the same
    tag are both kept. Duplicate ``(flags, value)`` pairs within a tag are
    collapsed to one.
    '''

    id = 'caa'
    _type = 'CAA'

    def merge(self, existing, record):
        # only handle CAA records; other record types pass through unchanged
        if record._type != self._type:
            return None
        by_tag = {}
        for value in existing.values:
            by_tag.setdefault(value.tag, {})[(value.flags, value.value)] = value
        merged = False
        for value in record.values:
            key = (value.flags, value.value)
            bucket = by_tag.get(value.tag)
            if bucket is None:
                by_tag[value.tag] = {key: value}
                merged = True
            elif key not in bucket:
                bucket[key] = value
                merged = True
        if not merged:
            return None
        values = []
        for tag in sorted(by_tag):
            values.extend(sorted(by_tag[tag].values()))
        return self._merged_record(existing, record, values)


class TxtMerger(BaseMerger):
    '''
    Merge TXT records by value union.

    Combines two TXT records that share a name and type into one, keeping
    every distinct text value from both. For example merging ``foo``
    (existing) with ``bar`` (incoming) yields a single TXT record with
    values ``['bar', 'foo']``.
    '''

    id = 'txt'
    _type = 'TXT'

    def merge(self, existing, record):
        # only handle TXT records; other record types pass through unchanged
        if record._type != self._type:
            return None
        values = {}
        for value in existing.values:
            values[str(value)] = value
        merged = False
        for value in record.values:
            key = str(value)
            if key not in values:
                merged = True
            values[key] = value
        if not merged:
            return None
        return self._merged_record(existing, record, sorted(values.values()))


# register the built-in mergers
for _merger in (CaaMerger(), TxtMerger()):
    REGISTRY.register(_merger)
del _merger
