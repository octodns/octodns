#
# Python 2/3 compat bits
#

try:  # pragma: no cover
    from StringIO import StringIO
except ImportError:  # pragma: no cover
    from io import StringIO

StringIO
