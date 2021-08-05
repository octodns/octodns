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

    def _process(self, zone, *args, **kwargs):
        ret = self._clone_zone(zone)
        for record in zone.records:
            # Uses a startswith rather than == to ignore subdomain challenges,
            # e.g. _acme-challenge.foo.domain.com when managing domain.com
            if record._type == 'TXT' and \
               record.name.startswith('_acme-challenge'):
                self.log.info('_process: ignoring %s', record.fqdn)
                continue
            ret.add_record(record)

        return ret

    process_source_zone = _process
    process_target_zone = _process
