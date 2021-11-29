#
# Ignores AWS ACM validation CNAME records.
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from logging import getLogger

from .base import BaseProcessor


class AwsAcmMangingProcessor(BaseProcessor):
    '''
    processors:
        awsacm:
        class: octodns.processor.acme.AwsAcmMangingProcessor

    ...

    zones:
        something.com.:
        ...
        processors:
        - awsacm
        ...
    '''

    log = getLogger('AwsAcmMangingProcessor')

    def _ignore_awsacm_cnames(self, zone):
        for r in zone.records:
            if r._type == 'CNAME' and \
                r.name.startswith('_') \
                    and r.value.endswith('.acm-validations.aws.'):
                self.log.info('_process: ignoring %s', r.fqdn)
                zone.remove_record(r)
        return zone

    def process_source_zone(self, desired, *args, **kwargs):
        return self._ignore_awsacm_cnames(desired)

    def process_target_zone(self, existing, *args, **kwargs):
        return self._ignore_awsacm_cnames(existing)
