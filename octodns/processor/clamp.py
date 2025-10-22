from logging import getLogger

from .base import BaseProcessor, ProcessorException


class TTLArgumentException(ProcessorException):
    pass


class TtlClampProcessor(BaseProcessor):
    """
    Processor that clamps TTL values to a specified range.

    Configuration:
        min_ttl: Minimum TTL value (default: 300 seconds / 5 minutes)
        max_ttl: Maximum TTL value (default: 86400 seconds / 24 hours)

    Example config.yaml:
        processors:
          clamp:
            class: octodns.processor.clamp.TtlClampProcessor
            min_ttl: 300
            max_ttl: 3600

        zones:
          example.com.:
            sources:
              - config
            processors:
              - clamp
            targets:
              - route53
    """

    def __init__(self, id, min_ttl=300, max_ttl=86400):
        super().__init__(id)
        self.log = getLogger(self.__class__.__name__)
        if not min_ttl <= max_ttl:
            raise TTLArgumentException(
                f'Min TTL {min_ttl} is not lower than max TTL {max_ttl}'
            )
        self.min_ttl = min_ttl
        self.max_ttl = max_ttl
        self.log.info('__init__: min=%ds, max=%ds', self.min_ttl, self.max_ttl)

    def process_source_zone(self, desired, sources):
        """
        Process records from source zone(s).

        Args:
            desired: Zone object containing the desired records
            sources: List of source names

        Returns:
            The modified zone
        """
        self.log.debug('process_source_zone: desired=%s', desired.name)

        for record in desired.records:
            original_ttl = record.ttl
            clamped_ttl = max(self.min_ttl, min(self.max_ttl, original_ttl))

            if clamped_ttl != original_ttl:
                self.log.info(
                    'process_source_zone: clamping TTL for %s (%s) %s -> %s',
                    record.fqdn,
                    record._type,
                    original_ttl,
                    clamped_ttl,
                )
                record.ttl = clamped_ttl

        return desired
