#
#
#

from warnings import warn


def deprecated(message, stacklevel=2):
    warn(message, DeprecationWarning, stacklevel=stacklevel)
