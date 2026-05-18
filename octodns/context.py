#
#
#

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Mapping


_K = TypeVar('_K')
_V = TypeVar('_V')


class ContextDict(dict[_K, _V]):
    '''
    This is used by things that call `Record.new` to pass in a `data`
    dictionary that includes some context as to where the data came from to be
    printed along with exceptions or validations of the record.

    It breaks lots of stuff if we stored the context in an extra key and the
    python `dict` object doesn't allow you to set attributes on the object so
    this is a very thin wrapper around `dict` that allows us to have a context
    attribute.
    '''

    def __init__(
        self, *args: Mapping[_K, _V] | None, context: Any = None, **kwargs: _V
    ) -> None:
        super().__init__(*args, **kwargs)
        self.context = context
