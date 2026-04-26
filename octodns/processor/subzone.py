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
    removing any record that the zone does not own per Zone.owns. NS
    records at the exact sub-zone boundary are preserved automatically
    because Zone.owns reports them as owned (they are the delegation
    glue and must stay in the parent).

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
        if not desired.sub_zones:
            return desired
        removed = 0
        for record in list(desired.records):
            if not desired.owns(record._type, record.fqdn):
                desired.remove_record(record)
                removed += 1
        if removed:
            self.log.info(
                'process_source_zone: removed %d sub-zone-owned record(s) from %s',
                removed,
                desired.name,
            )
        return desired
