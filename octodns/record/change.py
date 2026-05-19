#
#
#

from typing import Any

from ..equality import EqualityTupleMixin


class Change(EqualityTupleMixin):
    def __init__(self, existing: Any, new: Any) -> None:
        self.existing = existing
        self.new = new

    @property
    def record(self) -> Any:
        'Returns new if we have one, existing otherwise'
        return self.new or self.existing

    def _equality_tuple(self) -> tuple[int, str, str]:
        return (self.CLASS_ORDERING, self.record.name, self.record._type)


class Create(Change):
    CLASS_ORDERING = 1

    def __init__(self, new: Any) -> None:
        super().__init__(None, new)

    @property
    def data(self) -> dict[str, Any]:
        return {
            'type': 'create',
            'name': self.new.name,
            'new': self.new.data,
            'record_type': self.new._type,
        }

    def __repr__(self, leader: str = '') -> str:
        source = self.new.source.id if self.new.source else ''
        return f'Create {self.new} ({source})'


class Update(Change):
    CLASS_ORDERING = 2

    @property
    def data(self) -> dict[str, Any]:
        return {
            'type': 'update',
            'existing': self.existing.data,
            'name': self.new.name,
            'new': self.new.data,
            'record_type': self.new._type,
        }

    # Leader is just to allow us to work around heven eating leading whitespace
    # in our output. When we call this from the Manager.sync plan summary
    # section we'll pass in a leader, otherwise we'll just let it default and
    # do nothing
    def __repr__(self, leader: str = '') -> str:
        source = self.new.source.id if self.new.source else ''
        return (
            f'Update\n{leader}    {self.existing} ->\n'
            f'{leader}    {self.new} ({source})'
        )


class Delete(Change):
    CLASS_ORDERING = 0

    def __init__(self, existing: Any) -> None:
        super().__init__(existing, None)

    @property
    def data(self) -> dict[str, Any]:
        return {
            'type': 'delete',
            'existing': self.existing.data,
            'name': self.existing.name,
            'record_type': self.existing._type,
        }

    def __repr__(self, leader: str = '') -> str:
        return f'Delete {self.existing}'
