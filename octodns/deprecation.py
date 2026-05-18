#
#
#

from __future__ import annotations

from warnings import warn


def deprecated(message: str, stacklevel: int = 2) -> None:
    warn(message, DeprecationWarning, stacklevel=stacklevel)
