#
#
#

from .base import BaseProcessor, ProcessorException


class RestrictionException(ProcessorException):
    pass


class TtlRestrictionFilter(BaseProcessor):
    '''
    Ensure that configured TTLs are between a configured minimum and maximum or
    in an allowed set of values.

    The default minimum is 1 (the behavior of 0 is undefined spec-wise) and the
    default maximum is 604800 (seven days.) allowed_ttls is only used when
    explicitly configured and min and max are ignored in that case.

    Example usage:

    processors:
      min-max-ttl:
        class: octodns.processor.restrict.TtlRestrictionFilter
        min_ttl: 60
        max_ttl: 3600
        # allowed_ttls: [300, 900, 3600]

    zones:
      exxampled.com.:
        sources:
          - config
        processors:
          - min-max-ttl
        targets:
          - azure

    The restriction can be skipped for specific records by setting the lenient
    flag, e.g.

    a:
      octodns:
        lenient: true
      ttl: 0
      value: 1.2.3.4

    The higher level lenient flags are not checked as it would make more sense
    to just avoid enabling the processor in those cases.
    '''

    SEVEN_DAYS = 60 * 60 * 24 * 7

    def __init__(self, name, min_ttl=1, max_ttl=SEVEN_DAYS, allowed_ttls=None):
        super().__init__(name)
        self.min_ttl = min_ttl
        self.max_ttl = max_ttl
        self.allowed_ttls = set(allowed_ttls) if allowed_ttls else None

    def process_source_zone(self, zone, *args, **kwargs):
        for record in zone.records:
            if record.lenient:
                continue
            if self.allowed_ttls and record.ttl not in self.allowed_ttls:
                raise RestrictionException(
                    f'{record.fqdn} ttl={record.ttl} not an allowed value, allowed_ttls={self.allowed_ttls}'
                )
            elif record.ttl < self.min_ttl:
                raise RestrictionException(
                    f'{record.fqdn} ttl={record.ttl} too low, min_ttl={self.min_ttl}'
                )
            elif record.ttl > self.max_ttl:
                raise RestrictionException(
                    f'{record.fqdn} ttl={record.ttl} too high, max_ttl={self.max_ttl}'
                )
        return zone
