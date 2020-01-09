#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from shutil import rmtree
from tempfile import mkdtemp


class SimpleSource(object):

    def __init__(self, id='test'):
        pass


class SimpleProvider(object):
    SUPPORTS_ROOT_NS = False
    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS = set(('A',))
    id = 'test'

    def __init__(self, id='test'):
        pass

    def populate(self, zone, source=False, lenient=False):
        pass

    def supports(self, record):
        return True

    def __repr__(self):
        return self.__class__.__name__


class GeoProvider(object):
    SUPPORTS_ROOT_NS = False
    SUPPORTS_GEO = True
    SUPPORTS_DYNAMIC = False
    id = 'test'

    def __init__(self, id='test'):
        pass

    def populate(self, zone, source=False, lenient=False):
        pass

    def supports(self, record):
        return True

    def __repr__(self):
        return self.__class__.__name__


class DynamicProvider(object):
    SUPPORTS_ROOT_NS = False
    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = True
    id = 'test'

    def __init__(self, id='test'):
        pass

    def populate(self, zone, source=False, lenient=False):
        pass

    def supports(self, record):
        return True

    def __repr__(self):
        return self.__class__.__name__


class RootNsProvider(object):
    SUPPORTS_ROOT_NS = True
    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    id = 'test'

    def __init__(self, id='test'):
        pass

    def populate(self, zone, source=False, lenient=False):
        pass

    def supports(self, record):
        return True

    def __repr__(self):
        return self.__class__.__name__


class NoSshFpProvider(SimpleProvider):

    def supports(self, record):
        return record._type != 'SSHFP'


class TemporaryDirectory(object):

    def __init__(self, delete_on_exit=True):
        self.delete_on_exit = delete_on_exit

    def __enter__(self):
        self.dirname = mkdtemp()
        return self

    def __exit__(self, *args, **kwargs):
        if self.delete_on_exit:
            rmtree(self.dirname)
        else:
            raise Exception(self.dirname)
