from __future__ import annotations

from logging import getLogger
from typing import Any, Iterable

from ..zone import Zone
from .base import BaseProcessor


class AcmeManagingProcessor(BaseProcessor):
    log: Any = getLogger('AcmeManagingProcessor')

    def __init__(self, name: str, **kwargs: Any) -> None:
        '''
        Example configuration::

          processors:
            acme:
              class: octodns.processor.acme.AcmeManagingProcessor

          ...

          zones:
            something.com.:
            ...
            processors:
              - acme
            ...
        '''
        super().__init__(name, **kwargs)

        self._owned: set[Any] = set()

    def process_source_zone(
        self, desired: Zone, sources: Iterable[Any], lenient: bool = False
    ) -> Zone:
        lenient = self.lenient or lenient
        for record in desired.records:
            if (
                record._type == 'TXT'
                and record.name.startswith(  # type: ignore[attr-defined]
                    '_acme-challenge'
                )
            ):
                # We have a managed acme challenge record (owned by octoDNS) so
                # we should mark it as such
                record = record.copy()
                record.values.append('*octoDNS*')
                record.values.sort()
                # This assumes we'll see things as sources before targets,
                # which is the case...
                self._owned.add(record)
                desired.add_record(record, replace=True, lenient=lenient)
        return desired

    def process_target_zone(
        self, existing: Zone, target: Any, lenient: bool = False
    ) -> Zone:
        for record in existing.records:
            # Uses a startswith rather than == to ignore subdomain challenges,
            # e.g. _acme-challenge.foo.domain.com when managing domain.com
            if (
                record._type == 'TXT'
                and record.name.startswith('_acme-challenge')  # type: ignore[attr-defined]
                and '*octoDNS*' not in record.values
                and record not in self._owned
            ):
                self.log.info('_process: ignoring %s', record.fqdn)
                existing.remove_record(record)

        return existing


AcmeMangingProcessor = AcmeManagingProcessor
