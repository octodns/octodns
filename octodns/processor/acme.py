#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger

from .base import BaseProcessor


class AcmeIgnoringProcessor(BaseProcessor):
    log = getLogger('AcmeIgnoringProcessor')

    def __init__(self, name):
        super(AcmeIgnoringProcessor, self).__init__(name)

        self._owned = set()

    def process_source_zone(self, zone, *args, **kwargs):
        ret = self._clone_zone(zone)
        for record in zone.records:
            if record._type == 'TXT' and \
               record.name.startswith('_acme-challenge'):
                # We have a managed acme challenge record (owned by octoDNS) so
                # we should mark it as such
                record = record.copy()
                record.values.append('*octoDNS*')
                record.values.sort()
                self._owned.add(record)
            ret.add_record(record)
        return ret

    def process_target_zone(self, zone, *args, **kwargs):
        ret = self._clone_zone(zone)
        for record in zone.records:
            # Uses a startswith rather than == to ignore subdomain challenges,
            # e.g. _acme-challenge.foo.domain.com when managing domain.com
            if record._type == 'TXT' and \
               record.name.startswith('_acme-challenge') and \
               '*octoDNS*' not in record.values and \
               record not in self._owned:
                self.log.info('_process: ignoring %s', record.fqdn)
                continue
            ret.add_record(record)

        return ret
