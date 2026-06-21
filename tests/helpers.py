#
#
#

from contextlib import contextmanager
from logging import getLogger
from shutil import rmtree
from tempfile import mkdtemp

from octodns.processor.base import BaseProcessor
from octodns.provider.base import BaseProvider
from octodns.provider.yaml import YamlProvider
from octodns.record import Record
from octodns.record.validator import RecordValidator, ValueValidator
from octodns.secret.base import BaseSecrets
from octodns.zone import Zone
from octodns.zone.validator import ValidationReason, ZoneValidator


@contextmanager
def zone_validators_snapshot():
    reg = Zone.validators
    configured_snap = reg.configured
    active_snap = dict(reg.active)
    avail_snap = dict(reg.available)
    try:
        yield
    finally:
        reg.configured = configured_snap
        reg.active.clear()
        reg.active.update(active_snap)
        reg.available.clear()
        reg.available.update(avail_snap)


@contextmanager
def validators_snapshot():
    reg = Record.validators
    configured_snap = reg.configured
    active_record_snap = {k: dict(v) for k, v in reg.active_record.items()}
    active_value_snap = {k: dict(v) for k, v in reg.active_value.items()}
    avail_record_snap = {k: dict(v) for k, v in reg.available_record.items()}
    avail_value_snap = {k: dict(v) for k, v in reg.available_value.items()}
    try:
        yield
    finally:
        reg.configured = configured_snap
        reg.active_record.clear()
        reg.active_record.update(active_record_snap)
        reg.active_value.clear()
        reg.active_value.update(active_value_snap)
        reg.available_record.clear()
        reg.available_record.update(avail_record_snap)
        reg.available_value.clear()
        reg.available_value.update(avail_value_snap)


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

    def process_source_zone(self, zone, sources, lenient=False):
        self.count += len(zone.records)
        return zone


class TestRecordValidator(RecordValidator):
    def __init__(self, id, min_ttl=None, **kwargs):
        super().__init__(id, **kwargs)
        self.min_ttl = min_ttl

    def validate(self, record_cls, name, fqdn, data):
        if self.min_ttl and data.get('ttl', 0) < self.min_ttl:
            return [f'ttl must be at least {self.min_ttl}']
        return []


class TestValueValidator(ValueValidator):
    def __init__(self, id, **kwargs):
        super().__init__(id, **kwargs)

    def validate(self, value_cls, data, _type):
        return []


class NotAValidator:
    def __init__(self, id):
        self.id = id


class TestZoneValidator(ZoneValidator):
    def __init__(self, id, require_mx=False, **kwargs):
        super().__init__(id, **kwargs)
        self.require_mx = require_mx

    def validate(self, zone):
        if self.require_mx:
            mx_records = zone.get('', type='MX')
            if not mx_records:
                return [
                    ValidationReason('zone apex is missing an MX record', [])
                ]
        return []


class NotAZoneValidator:
    def __init__(self, id):
        self.id = id


class DummySecrets(BaseSecrets):
    def __init__(self, name, prefix):
        super().__init__(name)
        self.log.info('__init__: name=%s, prefix=%s', name, prefix)
        self.prefix = prefix

    def fetch(self, name, source):
        return f'{self.prefix}{name}'
