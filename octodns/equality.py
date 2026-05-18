#
#
#

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class _HasEqualityTuple(Protocol):
    def _equality_tuple(self) -> tuple[object, ...]: ...


class EqualityTupleMixin(object):
    def _equality_tuple(self) -> tuple[object, ...]:
        raise NotImplementedError('_equality_tuple method not implemented')

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _HasEqualityTuple):
            return NotImplemented
        return self._equality_tuple() == other._equality_tuple()

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, _HasEqualityTuple):
            return NotImplemented
        return self._equality_tuple() != other._equality_tuple()

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, _HasEqualityTuple):
            return NotImplemented
        return self._equality_tuple() < other._equality_tuple()

    def __le__(self, other: object) -> bool:
        if not isinstance(other, _HasEqualityTuple):
            return NotImplemented
        return self._equality_tuple() <= other._equality_tuple()

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, _HasEqualityTuple):
            return NotImplemented
        return self._equality_tuple() > other._equality_tuple()

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, _HasEqualityTuple):
            return NotImplemented
        return self._equality_tuple() >= other._equality_tuple()
