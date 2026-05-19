#
#
#

from typing import Callable, TypeVar
from warnings import warn

T = TypeVar('T', bound=Callable)


def deprecated(message: str, stacklevel: int = 2) -> Callable[[T], T]:
    warn(message, DeprecationWarning, stacklevel=stacklevel)
