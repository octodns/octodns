#
#
#

from logging import getLogger

from .base import BaseProcessor, ProcessorException


class SpfValueException(ProcessorException):
    pass


class SpfDnsLookupException(ProcessorException):
    pass


class SpfDnsLookupProcessor(BaseProcessor):
    log = getLogger('SpfDnsLookupProcessor')

    def __init__(self, name):
        self.log.debug(f"SpfDnsLookupProcessor: {name}")
        super().__init__(name)

    def process_source_zone(self, zone, *args, **kwargs):
        for record in zone.records:
            if record._type != 'TXT':
                continue

            if record._octodns.get('lenient'):
                continue

            # SPF values must begin with 'v=spf1 '
            values = [
                value for value in record.values if value.startswith('v=spf1 ')
            ]

            if len(values) == 0:
                continue

            if len(values) > 1:
                raise SpfValueException(
                    f"{record.fqdn} has more than one SPF value"
                )

            lookups = 0
            terms = values[0].removeprefix('v=spf1 ').split(' ')

            for term in terms:
                if lookups > 10:
                    raise SpfDnsLookupException(
                        f"{record.fqdn} has too many SPF DNS lookups"
                    )

                if term in ['a', 'mx', 'exists', 'redirect']:
                    lookups += 1

        return zone
