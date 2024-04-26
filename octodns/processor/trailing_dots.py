#
#
#

from octodns.processor.base import BaseProcessor


def _no_trailing_dot(record, prop):
    return any(getattr(v, prop)[-1] != '.' for v in record.values)


def _ensure_trailing_dots(record, prop):
    new = record.copy()
    for value in new.values:
        val = getattr(value, prop)
        if val[-1] != '.':
            # these will generally be str, but just in case we'll use the
            # constructor
            setattr(value, prop, val.__class__(f'{val}.'))
    return new


class EnsureTrailingDots(BaseProcessor):
    def process_source_zone(self, desired, sources):
        for record in desired.records:
            _type = record._type
            if _type in ('ALIAS', 'CNAME', 'DNAME') and record.value[-1] != '.':
                new = record.copy()
                # we need to preserve the value type (class) here and there's no
                # way to change a strings value, these all inherit from string,
                # so we need to create a new one of the same type
                new.value = new.value.__class__(f'{new.value}.')
                desired.add_record(new, replace=True)
            elif _type in ('NS', 'PTR') and any(
                v[-1] != '.' for v in record.values
            ):
                new = record.copy()
                klass = new.values[0].__class__
                new.values = [
                    v if v[-1] == '.' else klass(f'{v}.') for v in record.values
                ]
                desired.add_record(new, replace=True)
            elif _type == 'MX' and _no_trailing_dot(record, 'exchange'):
                new = _ensure_trailing_dots(record, 'exchange')
                desired.add_record(new, replace=True)
            elif _type == 'SRV' and _no_trailing_dot(record, 'target'):
                new = _ensure_trailing_dots(record, 'target')
                desired.add_record(new, replace=True)

        return desired
