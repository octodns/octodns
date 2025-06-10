#
#
#

from octodns.processor.base import BaseProcessor


class Templating(BaseProcessor):

    def __init__(self, id, *args, **kwargs):
        super().__init__(id, *args, **kwargs)

    def process_source_zone(self, desired, sources):
        sources = sources or []
        zone_params = {
            'zone_name': desired.decoded_name,
            'zone_decoded_name': desired.decoded_name,
            'zone_encoded_name': desired.name,
            'zone_num_records': len(desired.records),
            'zone_source_ids': ', '.join(s.id for s in sources),
        }

        def params(record):
            return {
                'record_name': record.decoded_name,
                'record_decoded_name': record.decoded_name,
                'record_encoded_name': record.name,
                'record_fqdn': record.decoded_fqdn,
                'record_decoded_fqdn': record.decoded_fqdn,
                'record_encoded_fqdn': record.fqdn,
                'record_type': record._type,
                'record_ttl': record.ttl,
                'record_source_id': record.source.id if record.source else None,
                **zone_params,
            }

        for record in desired.records:
            if hasattr(record, 'values'):
                new_values = [v.template(params(record)) for v in record.values]
                if record.values != new_values:
                    new = record.copy()
                    new.values = new_values
                    desired.add_record(new, replace=True)
            else:
                new_value = record.value.template(params(record))
                if record.value != new_value:
                    new = record.copy()
                    new.value = new_value
                    desired.add_record(new, replace=True)

        return desired
