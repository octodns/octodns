from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from ..provider.plan import Plan
from ..record import Record
from ..zone import Zone
from .base import BaseProcessor


# Mark anything octoDNS is managing that way it can know it's safe to modify or
# delete. We'll take ownership of existing records that we're told to manage
# and thus "own" them going forward.
class OwnershipProcessor(BaseProcessor):
    def __init__(
        self,
        name: str,
        txt_name: str = '_owner',
        txt_value: str = '*octodns*',
        txt_ttl: int = 60,
        should_replace: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(name, **kwargs)
        self.txt_name = txt_name
        self.txt_value = txt_value
        self.txt_ttl = txt_ttl
        self._txt_values: list[str] = [txt_value]
        self.should_replace = should_replace

    def process_source_zone(
        self, desired: Zone, sources: Iterable[Any], lenient: bool = False
    ) -> Zone:
        for record in desired.records:
            if self._is_ownership(record):
                # don't apply ownership to existing ownership recorcs, most
                # likely to see this in an alias zone that will be proccessed
                # once as the original and a 2nd time as the alias
                continue
            # Then create and add an ownership TXT for each of them
            record_name = record.name.replace('*', '_wildcard')  # type: ignore[attr-defined]
            if record.name:  # type: ignore[attr-defined]
                name = f'{self.txt_name}.{record._type}.{record_name}'  # type: ignore[attr-defined]
            else:
                name = f'{self.txt_name}.{record._type}'  # type: ignore[attr-defined]
            txt = Record.new(
                desired,
                name,
                {'type': 'TXT', 'ttl': self.txt_ttl, 'value': self.txt_value},
            )
            # add these w/lenient to cover the case when the ownership record
            # for a NS delegation record should technically live in the subzone
            desired.add_record(txt, lenient=True, replace=self.should_replace)

        return desired

    def _is_ownership(self, record: Any) -> bool:
        return (
            record._type == 'TXT'  # type: ignore[attr-defined]
            and record.name.startswith(self.txt_name)  # type: ignore[attr-defined]
            and record.values == self._txt_values  # type: ignore[attr-defined]
        )

    def process_plan(
        self,
        plan: Any,
        sources: Iterable[Any],
        target: Any,
        lenient: bool = False,
    ) -> Any:
        if not plan:
            # If we don't have any change there's nothing to do
            return plan

        # First find all the ownership info
        owned: dict[str, dict[str, bool]] = defaultdict(dict)
        # We need to look for ownership in both the desired and existing
        # states, many things will show up in both, but that's fine.
        for record in list(plan.existing.records) + list(plan.desired.records):
            if self._is_ownership(record):
                pieces = record.name.split('.', 2)  # type: ignore[attr-defined]
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

        filtered_changes: list[Any] = []
        for change in plan.changes:
            record = change.record

            if (
                not self._is_ownership(record)
                and record._type not in owned[record.name]  # type: ignore[attr-defined]
                and record.name != 'octodns-meta'  # type: ignore[attr-defined]
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
