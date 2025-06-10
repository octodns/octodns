#
#
#

from unittest import TestCase
from unittest.mock import call, patch

from octodns.processor.templating import Templating
from octodns.record import Record
from octodns.zone import Zone


def _find(zone, name):
    return next(r for r in zone.records if r.name == name)


class TemplatingTest(TestCase):
    def test_cname(self):
        templ = Templating('test')

        zone = Zone('unit.tests.', [])
        cname = Record.new(
            zone,
            'cname',
            {
                'type': 'CNAME',
                'ttl': 42,
                'value': '_cname.{zone_name}something.else.',
            },
            lenient=True,
        )
        zone.add_record(cname)
        noop = Record.new(
            zone,
            'noop',
            {
                'type': 'CNAME',
                'ttl': 42,
                'value': '_noop.nothing_to_do.something.else.',
            },
            lenient=True,
        )
        zone.add_record(noop)

        got = templ.process_source_zone(zone, None)
        cname = _find(got, 'cname')
        self.assertEqual('_cname.unit.tests.something.else.', cname.value)
        noop = _find(got, 'noop')
        self.assertEqual('_noop.nothing_to_do.something.else.', noop.value)

    def test_txt(self):
        templ = Templating('test')

        zone = Zone('unit.tests.', [])
        txt = Record.new(
            zone,
            'txt',
            {
                'type': 'TXT',
                'ttl': 42,
                'value': 'There are {zone_num_records} record(s) in {zone_name}',
            },
        )
        zone.add_record(txt)
        noop = Record.new(
            zone,
            'noop',
            {'type': 'TXT', 'ttl': 43, 'value': 'Nothing to template here.'},
        )
        zone.add_record(noop)

        got = templ.process_source_zone(zone, None)
        txt = _find(got, 'txt')
        self.assertEqual('There are 2 record(s) in unit.tests.', txt.values[0])
        noop = _find(got, 'noop')
        self.assertEqual('Nothing to template here.', noop.values[0])

    @patch('octodns.record.TxtValue.template')
    def test_params(self, mock_template):
        templ = Templating('test')

        class DummySource:

            def __init__(self, id):
                self.id = id

        zone = Zone('unit.tests.', [])
        record_source = DummySource('record')
        txt = Record.new(
            zone,
            'txt',
            {
                'type': 'TXT',
                'ttl': 42,
                'value': 'There are {zone_num_records} record(s) in {zone_name}',
            },
            source=record_source,
        )
        zone.add_record(txt)

        templ.process_source_zone(
            zone, sources=[record_source, DummySource('other')]
        )
        mock_template.assert_called_once()
        self.assertEqual(
            call(
                {
                    'record_name': 'txt',
                    'record_decoded_name': 'txt',
                    'record_encoded_name': 'txt',
                    'record_fqdn': 'txt.unit.tests.',
                    'record_decoded_fqdn': 'txt.unit.tests.',
                    'record_encoded_fqdn': 'txt.unit.tests.',
                    'record_type': 'TXT',
                    'record_ttl': 42,
                    'record_source_id': 'record',
                    'zone_name': 'unit.tests.',
                    'zone_decoded_name': 'unit.tests.',
                    'zone_encoded_name': 'unit.tests.',
                    'zone_num_records': 1,
                    'zone_source_ids': 'record, other',
                }
            ),
            mock_template.call_args,
        )
