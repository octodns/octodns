#
#
#

from logging import Logger, getLogger
from typing import TYPE_CHECKING, Iterable, Optional

if TYPE_CHECKING:
    from octodns.zone import Zone
    from octodns.record.base import Record
from .exception import ZoneException


class ZoneValidatorRegistry:
    log: Logger = getLogger('Zone')

    def __init__(self) -> None:
        self.available: dict[str, 'ZoneValidator'] = {}
        self.active: dict[str, 'ZoneValidator'] = {}
        self.configured: bool = False

    def register(self, validator: 'ZoneValidator') -> None:
        if not isinstance(validator, ZoneValidator):
            raise ZoneException(
                f'{validator.__class__.__name__} must be a ZoneValidator instance'
            )
        if validator.id in self.available:
            raise ZoneException(
                f'ZoneValidator id "{validator.id}" already registered'
            )
        self.available[validator.id] = validator

    def enable_sets(self, sets: Iterable[str]) -> None:
        self.configured = True
        self.active.clear()
        sets = set(sets)
        for validator in self.available.values():
            if validator.sets is None or sets & validator.sets:
                self.active[validator.id] = validator

    def enable(self, id: str) -> None:
        if id not in self.available:
            raise ZoneException(f'Unknown zone validator id "{id}"')
        self.active[id] = self.available[id]

    def disable(self, validator_id: str) -> bool:
        if validator_id.startswith('_'):
            raise ZoneException(
                f'Cannot disable bridge zone validator "{validator_id}"'
            )
        return self.active.pop(validator_id, None) is not None

    def reset_active(self) -> None:
        self.active.clear()

    def registered(self) -> list['ZoneValidator']:
        return list(self.active.values())

    def available_validators(self) -> list['ZoneValidator']:
        return list(self.available.values())

    def process_zone(self, zone: 'Zone') -> list['ValidationReason']:
        if not self.configured:
            self.log.warning(
                'process_zone: no zone validators configured, automatically enabling legacy set'
            )
            self.enable_sets({'legacy'})

        reasons = []
        for validator in self.active.values():
            reasons.extend(validator.validate(zone))

        return reasons


class ValidationReason:
    def __init__(self, reason: str, records: Iterable['Record']) -> None:
        self.reason = reason
        self.records: set['Record'] = set(records)

    @property
    def lenient(self) -> bool:
        return bool(self.records) and all(r.lenient for r in self.records)

    def __str__(self) -> str:
        msg = self.reason
        contexts = {
            r.context for r in self.records if getattr(r, 'context', None)
        }
        if contexts:
            msg += f" ({', '.join(sorted(contexts))})"
        return msg

    def __repr__(self) -> str:
        return self.reason


class ZoneValidator:
    '''
    Base class for zone-level validators.

    Subclasses override ``validate`` to return a list of ValidationReason
    objects describing any validation failures. An empty list indicates the
    zone is valid. The zone validator receives the fully assembled desired
    Zone and may examine any records within it. Because zone validators see
    the whole zone at once, they are suited for cross-record checks (e.g.
    requiring at least two MX values at the apex) that per-record validators
    cannot perform.

    Every zone validator instance has a non-empty ``id`` — a short, stable,
    kebab-case identifier (e.g. ``'multi-value-mx'``). Config-registered
    validators receive their config key as ``id`` automatically.
    '''

    def __init__(self, id: str, sets: Optional[Iterable[str]] = None) -> None:
        '''
        :param id: Non-empty identifier for this validator instance.
        :param sets: Iterable of set names, or ``None`` to always activate.
        '''
        if not id:
            raise ValueError(
                f'{self.__class__.__name__} requires a non-empty id'
            )
        self.id = id
        self.sets: Optional[set[str]] = set(sets) if sets is not None else None

    def validate(self, zone: 'Zone') -> list['ValidationReason']:
        '''
        Validate a fully populated zone.

        :param zone: The Zone to validate.
        :returns: list[ValidationReason] of reason objects; empty when valid.
        '''
        return []
