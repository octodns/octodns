#
#
#

from octodns.processor.base import BaseProcessor


class Templating(BaseProcessor):
    '''
    Record templating using python format. For simple records like TXT and CAA
    that is the value itself. For multi-field records like MX or SRV it's the
    text portions, exchange and target respectively.

    Example Processor Config:

        templating:
          class: octodns.processor.templating.Templating
          # Any k/v present in context will be passed into the .format method and
          # thus be available as additional variables in the template. This is all
          # optional.
          context:
            key: value
            another: 42

    Example Records:

        foo:
          type: TXT
          value: The zone this record lives in is {zone_name}. There are {zone_num_records} record(s).

        bar:
          type: MX
          values:
            - preference: 1
              exchange: mx1.{zone_name}.mail.mx.
            - preference: 1
              exchange: mx2.{zone_name}.mail.mx.

    Note that validations for some types reject values with {}. When
    encountered the best option is to use record level `lenient: true`
    https://github.com/octodns/octodns/blob/main/docs/records.md#lenience

    Note that if you need to add dynamic context you can create a custom
    processor that inherits from Templating and passes them into the call to
    super, e.g.

        class MyTemplating(Templating):
            def __init__(self, *args, context={}, **kwargs):
                context['year'] = lambda desired, sources: datetime.now().strftime('%Y')
                super().__init__(*args, context, **kwargs)

    See https://docs.python.org/3/library/string.html#custom-string-formatting
    for details on formatting options. Anything possible in an `f-string` or
    `.format` should work here.

    '''

    def __init__(self, id, *args, context={}, **kwargs):
        super().__init__(id, *args, **kwargs)
        self.context = context

    def process_source_zone(self, desired, sources):
        sources = sources or []
        zone_params = {
            'zone_name': desired.decoded_name.rstrip('.'),
            'zone_decoded_name': desired.decoded_name.rstrip('.'),
            'zone_encoded_name': desired.name.rstrip('.'),
            'zone_num_records': len(desired.records),
            'zone_source_ids': ', '.join(s.id for s in sources),
            # add any extra context provided to us, if the value is a callable
            # object call it passing our params so that arbitrary dynamic
            # context can be added for use in formatting
            **{
                k: (v(desired, sources) if callable(v) else v)
                for k, v in self.context.items()
            },
        }

        def params(record):
            return {
                'record_name': record.decoded_name,
                'record_decoded_name': record.decoded_name,
                'record_encoded_name': record.name,
                'record_fqdn': record.decoded_fqdn.rstrip('.'),
                'record_decoded_fqdn': record.decoded_fqdn.rstrip('.'),
                'record_encoded_fqdn': record.fqdn.rstrip('.'),
                'record_type': record._type,
                'record_ttl': record.ttl,
                'record_source_id': record.source.id if record.source else None,
                **zone_params,
            }

        for record in desired.records:
            if hasattr(record, 'values'):
                if record.values and not hasattr(record.values[0], 'template'):
                    # the (custom) value type does not support templating
                    continue
                new_values = [v.template(params(record)) for v in record.values]
                if record.values != new_values:
                    new = record.copy()
                    new.values = new_values
                    desired.add_record(new, replace=True)
            else:
                if not hasattr(record.value, 'template'):
                    # the (custom) value type does not support templating
                    continue
                new_value = record.value.template(params(record))
                if record.value != new_value:
                    new = record.copy()
                    new.value = new_value
                    desired.add_record(new, replace=True)

        return desired
