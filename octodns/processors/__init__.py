#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from ..zone import Zone


class BaseProcessor(object):

    def __init__(self, name):
        self.name = name

    def _create_zone(self, zone):
        return Zone(zone.name, sub_zones=zone.sub_zones)
