#
#
#

from logging import getLogger
from shutil import rmtree
from tempfile import mkdtemp

from octodns.processor.base import BaseProcessor
from octodns.provider.base import BaseProvider
from octodns.provider.yaml import YamlProvider
from octodns.secret.base import BaseSecrets


class SimpleSource(object):
    def __init__(self, id='test'):
        pass


class SimpleProvider(object):
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
    SUPPORTS_GEO = True
    SUPPORTS_DYNAMIC = False
    SUPPORTS = set(('A', 'AAAA', 'TXT'))
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
    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = True
    SUPPORTS = set(('A', 'AAAA', 'TXT'))
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


class WantsConfigProcessor(BaseProcessor):
    def __init__(self, name, some_config):
        super().__init__(name)


class PlannableProvider(BaseProvider):
    log = getLogger('PlannableProvider')

    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS = set(('A', 'AAAA', 'TXT'))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def populate(self, zone, source=False, target=False, lenient=False):
        pass

    def supports(self, record):
        return True

    def __repr__(self):
        return self.__class__.__name__


class TestYamlProvider(YamlProvider):
    pass


class TestBaseProcessor(BaseProcessor):
    pass


class CountingProcessor(BaseProcessor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.count = 0

    def process_source_zone(self, zone, *args, **kwargs):
        self.count += len(zone.records)
        return zone


class DummySecrets(BaseSecrets):
    def __init__(self, name, prefix):
        super().__init__(name)
        self.log.info('__init__: name=%s, prefix=%s', name, prefix)
        self.prefix = prefix

    def fetch(self, name, source):
        return f'{self.prefix}{name}'
