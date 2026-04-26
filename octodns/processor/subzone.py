#
#
#

from logging import getLogger

from .base import BaseProcessor


class SubzoneOverlapFilter(BaseProcessor):
    '''Strip records from a parent zone that belong in a configured sub-zone.

    Zone.add_record already enforces sub-zone ownership and raises
    SubzoneRecordException when a non-NS/DS record's name falls under a
    configured sub-zone. That check is downgraded to a warning when the
    record (or the call) is lenient, which is common for sources that
    over-fetch (e.g. an IPAM source returning every address in a parent
    prefix when a more-specific child zone is also configured). In that
    case the offending records survive populate and end up in both the
    parent and the child zone files.

    This processor restores the strict behaviour after populate by
    removing records that fall under a configured sub-zone. It mirrors
    Zone.add_record's own rules:

    - NS and DS records at the exact sub-zone boundary are preserved
      (they are the legitimate delegation glue and must stay in the
      parent).
    - Records explicitly marked with record-level lenient (e.g.
      ``octodns: { lenient: true }`` in a YAML config) are preserved.
      This covers the operator-opt-in case in
      https://github.com/octodns/octodns/issues/1362 -- glue records
      like ``ns.sub.domain.tld.`` that genuinely belong in the parent
      zone file even though they sit under a delegated sub-zone.

    The processor takes no configuration; it relies entirely on the
    sub_zones the manager already populates on each Zone from the
    configured zones map.

    Example usage::

      processors:
        subzone-overlap:
          class: octodns.processor.subzone.SubzoneOverlapFilter

      zones:
        10.in-addr.arpa.:
          sources:
            - some-ipam-source
          processors:
            - subzone-overlap
          targets:
            - bind
        1.10.in-addr.arpa.:
          sources:
            - some-ipam-source
          targets:
            - bind
    '''

    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.log = getLogger(f'SubzoneOverlapFilter[{name}]')

    def process_source_zone(self, desired, sources, lenient=False):
        sub_zones = desired.sub_zones
        if not sub_zones:
            return desired
        sub_suffixes = tuple(f'.{s}' for s in sub_zones)
        removed = 0
        for record in list(desired.records):
            # Operator-opt-in: a record marked lenient is one the user
            # explicitly asked to keep here (e.g. delegation glue).
            if record.lenient:
                continue
            name = record.name
            # NS and DS at the exact sub-zone boundary are the legitimate
            # delegation glue. Mirror Zone.add_record's allowance (Zone.owns
            # only special-cases NS, hence the explicit check for DS).
            if name in sub_zones and record._type in ('NS', 'DS'):
                continue
            if name in sub_zones or name.endswith(sub_suffixes):
                desired.remove_record(record)
                removed += 1
        if removed:
            self.log.info(
                'process_source_zone: removed %d sub-zone-owned record(s) from %s',
                removed,
                desired.name,
            )
        return desired
