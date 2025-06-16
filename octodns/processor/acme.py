#
#
#

from logging import getLogger

from .base import BaseProcessor


class AcmeManagingProcessor(BaseProcessor):
    log = getLogger("AcmeManagingProcessor")

    def __init__(self, name):
        """Manage or ignore ACME records.

        **ACME records in the source:**
            Will be marked with metadata so octodns knows they are managed by octodns.

        **ACME records in the target:**
            If the octodns mark **IS NOT** found, they will be ignored. So ACME records in the
            target will not be updated or deleted.

            If the octodns mark **IS** found, they will be treated like normal records.

        Note
        ----
        This filter processes records with names starting with: `_acme-challenge`,
        mostly used for the DNS-01 challenge.

        For example: `_acme-challenge.foo.domain.com`

        References
        ---------
        https://letsencrypt.org/docs/challenge-types/#dns-01-challenge

        Example
        -------
        .. code-block:: yaml

            processors:
                acme:
                    class: octodns.processor.acme.AcmeManagingProcessor

            zones:
                something.com.:
                    sources:
                        - x
                    processors:
                        - acme
                    targets:
                        - y
        """
        super().__init__(name)

        self._owned = set()

    def process_source_zone(self, desired, *args, **kwargs):
        for record in desired.records:
            if record._type == "TXT" and record.name.startswith(
                "_acme-challenge"
            ):
                # We have a managed acme challenge record (owned by octoDNS) so
                # we should mark it as such
                record = record.copy()
                record.values.append("*octoDNS*")
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
                record._type == "TXT"
                and record.name.startswith("_acme-challenge")
                and "*octoDNS*" not in record.values
                and record not in self._owned
            ):
                self.log.info("_process: ignoring %s", record.fqdn)
                existing.remove_record(record)

        return existing


AcmeMangingProcessor = AcmeManagingProcessor
