#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from ..record import Record

from . import BaseProcessor


class OwnershipProcessor(BaseProcessor):

    def __init__(self, name, txt_name='_owner'):
        super(OwnershipProcessor, self).__init__(name)
        self.txt_name = txt_name

    def add_ownerships(self, zone):
        ret = self._create_zone(zone)
        for record in zone.records:
            ret.add_record(record)
            name = '{}.{}.{}'.format(self.txt_name, record._type, record.name),
            txt = Record.new(zone, name, {
                                 'type': 'TXT',
                                 'ttl': 60,
                                 'value': 'octodns',
                             })
            ret.add_record(txt)

        return ret

    def remove_unowned(self, zone):
        ret = self._create_zone(zone)
        return ret

    def process(self, zone, target=False):
        if target:
            return self.remove_unowned(zone)
        return self.add_ownerships(zone)
