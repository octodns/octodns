#
#
#

from logging import getLogger

from .base import BaseProcessor


class AcmeMangingProcessor(BaseProcessor):
    log = getLogger('AcmeMangingProcessor')

    def __init__(self, name):
        '''
        processors:
          acme:
            class: octodns.processor.acme.AcmeMangingProcessor

        ...

        zones:
          something.com.:
          ...
          processors:
            - acme
          ...
        '''
        super().__init__(name)

        self._owned = set()

    def process_source_zone(self, desired, *args, **kwargs):
        for record in desired.records:
            if record._type == 'TXT' and record.name.startswith(
                '_acme-challenge'
            ):
                # We have a managed acme challenge record (owned by octoDNS) so
                # we should mark it as such
                record = record.copy()
                record.values.append('*octoDNS*')
                record.values.sort()
                # This assumes we'll see things as sources before targets,
                # which is the case...
                self._owned.add(record)
                desired.add_record(record, replace=True)
        return desired

    def process_target_zone(self, existing, *args, **kwargs):
        for record in existing.records:
            # Uses a startswith rather than == to ignore subdomain challenges,
            # e.g. _acme-challenge.foo.domain.com when managing domain.com
            if (
                record._type == 'TXT'
                and record.name.startswith('_acme-challenge')
                and '*octoDNS*' not in record.values
                and record not in self._owned
            ):
                self.log.info('_process: ignoring %s', record.fqdn)
                existing.remove_record(record)

        return existing
