#
#
#

from __future__ import annotations

from typing import Any, Protocol


class _HasRecordAttributes(Protocol):
    name: str
    _type: str
    source: Any
    data: dict[str, Any]


class Change(object):
    CLASS_ORDERING: int
    existing: _HasRecordAttributes | None
    new: _HasRecordAttributes | None

    def __init__(
        self,
        existing: _HasRecordAttributes | None,
        new: _HasRecordAttributes | None,
    ) -> None:
        # One of existing or new must be provided (not both None)
        if existing is None and new is None:
            raise ValueError('Either existing or new must be provided')
        self.existing = existing
        self.new = new

    @property
    def record(self) -> _HasRecordAttributes:
        'Returns new if we have one, existing otherwise'
        # One of existing or new must be provided (checked in __init__)
        if self.new is not None:
            return self.new
        # mypy doesn't narrow the type of self.existing here, so use assert
        assert self.existing is not None
        return self.existing

    def _equality_tuple(self) -> tuple[int, str, str]:
        r = self.record
        return (self.CLASS_ORDERING, r.name, r._type)

    def __lt__(self, other: Change) -> bool:
        self_tuple = (self.CLASS_ORDERING, self.record.name, self.record._type)
        other_tuple = (
            other.CLASS_ORDERING,
            other.record.name,
            other.record._type,
        )
        return self_tuple < other_tuple

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Change):
            return False
        return self._equality_tuple() == other._equality_tuple()

    def __hash__(self) -> int:
        return hash(self._equality_tuple())


class Create(Change):
    CLASS_ORDERING = 1

    def __init__(self, new: _HasRecordAttributes) -> None:
        super().__init__(None, new)

    @property
    def data(self) -> dict[str, Any]:
        n = self.new
        assert n is not None
        return {
            'type': 'create',
            'name': n.name,
            'new': n.data,
            'record_type': n._type,
        }

    def __repr__(self, leader: str = '') -> str:
        n = self.new
        assert n is not None
        source = n.source.id if n.source else ''
        return f'Create {n} ({source})'


class Update(Change):
    CLASS_ORDERING = 2

    @property
    def data(self) -> dict[str, Any]:
        e = self.existing
        n = self.new
        assert e is not None and n is not None
        return {
            'type': 'update',
            'existing': e.data,
            'name': n.name,
            'new': n.data,
            'record_type': n._type,
        }

    # Leader is just to allow us to work around heven eating leading whitespace
    # in our output. When we call this from the Manager.sync plan summary
    # section we'll pass in a leader, otherwise we'll just let it default and
    # do nothing
    def __repr__(self, leader: str = '') -> str:
        e = self.existing
        n = self.new
        assert e is not None and n is not None
        source = n.source.id if n.source else ''
        return f'Update\n{leader}    {e} ->\n' f'{leader}    {n} ({source})'


class Delete(Change):
    CLASS_ORDERING = 0

    def __init__(self, existing: _HasRecordAttributes) -> None:
        super().__init__(existing, None)

    @property
    def data(self) -> dict[str, Any]:
        e = self.existing
        assert e is not None
        return {
            'type': 'delete',
            'existing': e.data,
            'name': e.name,
            'record_type': e._type,
        }

    def __repr__(self, leader: str = '') -> str:
        return f'Delete {self.existing}'
