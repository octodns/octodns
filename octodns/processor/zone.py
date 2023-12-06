#
#
#

from logging import getLogger

from .base import BaseProcessor, ProcessorException


class DynamicZoneConfigProcessor(BaseProcessor):
    log = getLogger('DynamicZoneConfigProcessor')

    def process_zone_config(self, zones, get_sources):
        for name, config in list(zones.items()):
            if not name.startswith('*'):
                continue
            # we've found a dynamic config element

            # find its sources
            found_sources = get_sources(name, config)

            self.log.info(
                'sync:   dynamic zone=%s, sources=%s', name, found_sources
            )
            for source in found_sources:
                if not hasattr(source, 'list_zones'):
                    raise ProcessorException(
                        f'dynamic zone={name} includes a source, {source.id}, that does not support `list_zones`'
                    )
                for zone_name in source.list_zones():
                    if zone_name in zones:
                        self.log.info(
                            'sync:      zone=%s already in config, ignoring',
                            zone_name,
                        )
                        continue
                    self.log.info(
                        'sync:      adding dynamic zone=%s', zone_name
                    )
                    zones[zone_name] = config

            # remove the dynamic config element so we don't try and populate it
            del zones[name]

        return zones
