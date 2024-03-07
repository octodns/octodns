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
            setattr(value, prop, f'{val}.')
    return new


class EnsureTrailingDots(BaseProcessor):
    def process_source_zone(self, desired, sources):
        for record in desired.records:
            _type = record._type
            if _type in ('ALIAS', 'CNAME', 'DNAME') and record.value[-1] != '.':
                new = record.copy()
                new.value = f'{new.value}.'
                desired.add_record(new, replace=True)
            elif _type in ('NS', 'PTR') and any(
                v[-1] != '.' for v in record.values
            ):
                new = record.copy()
                new.values = [
                    v if v[-1] == '.' else f'{v}.' for v in record.values
                ]
                desired.add_record(new, replace=True)
            elif _type == 'MX' and _no_trailing_dot(record, 'exchange'):
                new = _ensure_trailing_dots(record, 'exchange')
                desired.add_record(new, replace=True)
            elif _type == 'SRV' and _no_trailing_dot(record, 'target'):
                new = _ensure_trailing_dots(record, 'target')
                desired.add_record(new, replace=True)

        return desired
