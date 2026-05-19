#
#
#


from typing import Any


class EqualityTupleMixin(object):
    def _equality_tuple(self) -> tuple[Any, ...]:
        raise NotImplementedError('_equality_tuple method not implemented')

    def __eq__(self, other: Any) -> bool:
        return self._equality_tuple() == other._equality_tuple()  # type: ignore[no-any-return]

    def __ne__(self, other: Any) -> bool:
        return self._equality_tuple() != other._equality_tuple()  # type: ignore[no-any-return]

    def __lt__(self, other: Any) -> bool:
        return self._equality_tuple() < other._equality_tuple()  # type: ignore[no-any-return]

    def __le__(self, other: Any) -> bool:
        return self._equality_tuple() <= other._equality_tuple()  # type: ignore[no-any-return]

    def __gt__(self, other: Any) -> bool:
        return self._equality_tuple() > other._equality_tuple()  # type: ignore[no-any-return]

    def __ge__(self, other: Any) -> bool:
        return self._equality_tuple() >= other._equality_tuple()  # type: ignore[no-any-return]
