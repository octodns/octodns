#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

import logging

from .base import BaseProvider


class DeleteProvider(BaseProvider):
    '''
    Core provider for records configured in yaml files on disk.

    config:
        class: octodns.provider.delete.DeleteProvider
    '''
    SUPPORTS_GEO = True
    SUPPORTS = set(('A', 'AAAA', 'ALIAS', 'CAA', 'CNAME', 'MX', 'NAPTR', 'NS',
                    'PTR', 'SSHFP', 'SPF', 'SRV', 'TXT'))

    def __init__(self, id, *args, **kwargs):
        self.log = logging.getLogger('DeleteProvider[{}]'.format(id))
        self.log.debug('__init__: id=%s', id)
        super(DeleteProvider, self).__init__(id, *args, **kwargs)

    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s, target=%s, lenient=%s', zone.name,
                       target, lenient)

        zone.flag_for_deletion()

        return

    def _apply(self, plan):

        return
