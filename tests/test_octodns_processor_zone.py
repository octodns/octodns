#
#
#

from unittest import TestCase

from octodns.processor.base import ProcessorException
from octodns.processor.zone import DynamicZoneConfigProcessor


class _GetSourcesMock:
    def __init__(self, sources=[]):
        self.data = {}
        self.sources = sources
        self.called = 0

    def get_sources(self, name, config):
        self.data[name] = config
        self.called += 1
        return self.sources


class _ListZonesMock:
    id = '_ListZonesMock'

    def __init__(self, zones):
        self.zones = zones
        self.called = 0

    def list_zones(self):
        self.called += 1
        return self.zones


class _NoListZonesMock:
    id = '_NoListZonesMock'


class BaseProcessorTest(TestCase):
    proc = DynamicZoneConfigProcessor('test')

    def test_process_zone_config_empty(self):
        mock = _GetSourcesMock()

        zones = {}
        got = self.proc.process_zone_config(zones, mock.get_sources)
        self.assertFalse(mock.called)
        self.assertIs(zones, got)

    def test_process_zone_config_static(self):
        mock = _GetSourcesMock()

        zones = {'unit.tests.': {'key': 'value'}}
        got = self.proc.process_zone_config(zones, mock.get_sources)
        self.assertFalse(mock.called)
        self.assertIs(zones, got)

    def test_process_zone_config_dynamic(self):
        lz_mock = _ListZonesMock(
            [
                'dynamic1.unit.tests.',
                'dynamic2.unit.tests.',
                'existing.unit.tests.',
            ]
        )
        gs_mock = _GetSourcesMock([lz_mock])

        zones = {
            '*': {'type': 'dynamic'},
            'unit.tests.': {'type': 'static'},
            'existing.unit.tests.': {'type': 'exsiting'},
        }
        got = self.proc.process_zone_config(zones, gs_mock.get_sources)
        self.assertEqual(1, gs_mock.called)
        self.assertEqual({'*': {'type': 'dynamic'}}, gs_mock.data)
        self.assertEqual(1, lz_mock.called)

        self.assertIs(zones, got)
        self.assertEqual({'type': 'dynamic'}, got['dynamic1.unit.tests.'])
        self.assertEqual({'type': 'dynamic'}, got['dynamic2.unit.tests.'])

    def test_process_zone_config_dynamic_prefix(self):
        lz_mock = _ListZonesMock(['dyn-pre.unit.tests.'])
        gs_mock = _GetSourcesMock([lz_mock])

        zones = {'*.foo': {'type': 'dynamic-too'}}
        got = self.proc.process_zone_config(zones, gs_mock.get_sources)
        self.assertEqual(1, gs_mock.called)
        self.assertEqual({'*.foo': {'type': 'dynamic-too'}}, gs_mock.data)
        self.assertEqual(1, lz_mock.called)

        self.assertIs(zones, got)
        from pprint import pprint

        pprint(got)
        self.assertEqual({'type': 'dynamic-too'}, got['dyn-pre.unit.tests.'])

    def test_process_zone_config_no_list_zones(self):
        gs_mock = _GetSourcesMock([_NoListZonesMock()])

        zones = {'*': {'type': 'dynamic'}}
        with self.assertRaises(ProcessorException) as ctx:
            self.proc.process_zone_config(zones, gs_mock.get_sources)
        self.assertEqual(
            'dynamic zone=* includes a source, _NoListZonesMock, that does not support `list_zones`',
            str(ctx.exception),
        )
