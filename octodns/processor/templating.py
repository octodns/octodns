#
#
#

from octodns.processor.base import BaseProcessor


class TemplatingError(Exception):

    def __init__(self, record, msg):
        self.record = record
        msg = f'Invalid record "{record.fqdn}", {msg}'
        super().__init__(msg)


class Templating(BaseProcessor):
    '''
    Record templating using python format. For simple records like TXT and CAA
    that is the value itself. For multi-field records like MX or SRV it's the
    text portions, exchange and target respectively.

    Example Processor Config::

      templating:
        class: octodns.processor.templating.Templating
        # When `trailing_dots` is disabled, trailing dots are removed from all
        # built-in variables values who represent a FQDN, like `{zone_name}`
        # or `{record_fqdn}`. Optional. Default to `True`.
        trailing_dots: False
        # Any k/v present in context will be passed into the .format method and
        # thus be available as additional variables in the template. This is all
        # optional.
        context:
          key: value
          another: 42

    Example Records::

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
    super, e.g.::

      class MyTemplating(Templating):
          def __init__(self, *args, context={}, **kwargs):
              context['year'] = lambda desired, sources: datetime.now().strftime('%Y')
              super().__init__(*args, context, **kwargs)

    See https://docs.python.org/3/library/string.html#custom-string-formatting
    for details on formatting options. Anything possible in an `f-string` or
    `.format` should work here.
    '''

    def __init__(self, id, *args, trailing_dots=True, context={}, **kwargs):
        super().__init__(id, *args, **kwargs)
        self.trailing_dots = trailing_dots
        self.context = context

    def process_source_and_target_zones(self, desired, existing, provider):
        zone_name = desired.decoded_name
        zone_decoded_name = desired.decoded_name
        zone_encoded_name = desired.name
        if not self.trailing_dots:
            zone_name = zone_name[:-1]
            zone_decoded_name = zone_decoded_name[:-1]
            zone_encoded_name = zone_encoded_name[:-1]
        zone_params = {
            'zone_name': zone_name,
            'zone_decoded_name': zone_decoded_name,
            'zone_encoded_name': zone_encoded_name,
            'zone_num_records': len(desired.records),
            # add any extra context provided to us, if the value is a callable
            # object call it passing our params so that arbitrary dynamic
            # context can be added for use in formatting
            **{
                k: (v(desired, provider) if callable(v) else v)
                for k, v in self.context.items()
            },
        }

        def build_params(record):
            record_fqdn = record.decoded_fqdn
            record_decoded_fqdn = record.decoded_fqdn
            record_encoded_fqdn = record.fqdn
            if not self.trailing_dots:
                record_fqdn = record_fqdn[:-1]
                record_decoded_fqdn = record_decoded_fqdn[:-1]
                record_encoded_fqdn = record_encoded_fqdn[:-1]
            return {
                'record_name': record.decoded_name,
                'record_decoded_name': record.decoded_name,
                'record_encoded_name': record.name,
                'record_fqdn': record_fqdn,
                'record_decoded_fqdn': record_decoded_fqdn,
                'record_encoded_fqdn': record_encoded_fqdn,
                'record_type': record._type,
                'record_ttl': record.ttl,
                'record_source_id': record.source.id if record.source else None,
                **zone_params,
            }

        def template(value, params, record):
            try:
                return value.template(params)
            except KeyError as e:
                raise TemplatingError(
                    record,
                    f'undefined template parameter "{e.args[0]}" in value',
                ) from e

        for record in desired.records:
            params = build_params(record)
            if hasattr(record, 'values'):
                if record.values and not hasattr(record.values[0], 'template'):
                    # the (custom) value type does not support templating
                    continue
                new_values = [
                    template(v, params, record) for v in record.values
                ]
                if record.values != new_values:
                    new = record.copy()
                    new.values = new_values
                    desired.add_record(new, replace=True)
            else:
                if not hasattr(record.value, 'template'):
                    # the (custom) value type does not support templating
                    continue
                new_value = template(record.value, params, record)
                if record.value != new_value:
                    new = record.copy()
                    new.value = new_value
                    desired.add_record(new, replace=True)

        return desired, existing
