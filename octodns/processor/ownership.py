#
#
#

from collections import defaultdict

from ..provider.plan import Plan
from ..record import Record
from .base import BaseProcessor


# Mark anything octoDNS is managing that way it can know it's safe to modify or
# delete. We'll take ownership of existing records that we're told to manage
# and thus "own" them going forward.
class OwnershipProcessor(BaseProcessor):
    def __init__(self, name, txt_name='_owner', txt_value='*octodns*'):
        super().__init__(name)
        self.txt_name = txt_name
        self.txt_value = txt_value
        self._txt_values = [txt_value]

    def process_source_zone(self, desired, *args, **kwargs):
        for record in desired.records:
            # Then create and add an ownership TXT for each of them
            record_name = record.name.replace('*', '_wildcard')
            if record.name:
                name = f'{self.txt_name}.{record._type}.{record_name}'
            else:
                name = f'{self.txt_name}.{record._type}'
            txt = Record.new(
                desired,
                name,
                {'type': 'TXT', 'ttl': 60, 'value': self.txt_value},
            )
            # add these w/lenient to cover the case when the ownership record
            # for a NS delegation record should technically live in the subzone
            desired.add_record(txt, lenient=True)

        return desired

    def _is_ownership(self, record):
        return (
            record._type == 'TXT'
            and record.name.startswith(self.txt_name)
            and record.values == self._txt_values
        )

    def process_plan(self, plan, *args, **kwargs):
        if not plan:
            # If we don't have any change there's nothing to do
            return plan

        # First find all the ownership info
        owned = defaultdict(dict)
        # We need to look for ownership in both the desired and existing
        # states, many things will show up in both, but that's fine.
        for record in list(plan.existing.records) + list(plan.desired.records):
            if self._is_ownership(record):
                pieces = record.name.split('.', 2)
                if len(pieces) > 2:
                    _, _type, name = pieces
                    name = name.replace('_wildcard', '*')
                else:
                    _type = pieces[1]
                    name = ''
                owned[name][_type.upper()] = True

        # Cases:
        # - Configured in source
        #   - We'll fully CRU/manage it adding ownership TXT,
        #     thanks to process_source_zone, if needed
        # - Not in source
        #   - Has an ownership TXT - delete it & the ownership TXT
        #   - Does not have an ownership TXT - don't delete it
        # - Special records like octodns-meta
        #   - Should be left alone and should not have ownerthis TXTs

        filtered_changes = []
        for change in plan.changes:
            record = change.record

            if (
                not self._is_ownership(record)
                and record._type not in owned[record.name]
                and record.name != 'octodns-meta'
            ):
                # It's not an ownership TXT, it's not owned, and it's not
                # special we're going to ignore it
                continue

            # We own this record or owned it up until now so whatever the
            # change is we should do
            filtered_changes.append(change)

        if not filtered_changes:
            return None
        elif plan.changes != filtered_changes:
            return Plan(
                plan.existing,
                plan.desired,
                filtered_changes,
                plan.exists,
                plan.update_pcent_threshold,
                plan.delete_pcent_threshold,
            )

        return plan
