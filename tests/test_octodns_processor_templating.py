#
#
#

from unittest import TestCase
from unittest.mock import call, patch

from octodns.processor.templating import Templating, TemplatingError
from octodns.record import Record, ValueMixin, ValuesMixin
from octodns.zone import Zone


class DummySource:

    def __init__(self, id):
        self.id = str(id)


class CustomValue(str):

    @classmethod
    def validate(cls, *args, **kwargs):
        return []

    @classmethod
    def process(cls, v):
        if isinstance(v, (list, tuple)):
            return (CustomValue(i) for i in v)
        return CustomValue(v)

    @classmethod
    def parse_rdata_text(cls, *args, **kwargs):
        pass

    def __init__(self, *args, **kwargs):
        self._asked_for = set()

    def rdata_text(self):
        pass

    def __getattr__(self, item):
        self._asked_for.add(item)
        raise AttributeError('nope')


class Single(ValueMixin, Record):
    _type = 'S'
    _value_type = CustomValue


Record.register_type(Single, 'S')


class Multiple(ValuesMixin, Record):
    _type = 'M'
    _value_type = CustomValue


Record.register_type(Multiple, 'M')


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

        got, _ = templ.process_source_and_target_zones(zone, None, None)
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

        got, _ = templ.process_source_and_target_zones(zone, None, None)
        txt = _find(got, 'txt')
        self.assertEqual('There are 2 record(s) in unit.tests.', txt.values[0])
        noop = _find(got, 'noop')
        self.assertEqual('Nothing to template here.', noop.values[0])

    def test_no_template(self):
        templ = Templating('test')

        zone = Zone('unit.tests.', [])
        s = Record.new(zone, 's', {'type': 'S', 'ttl': 42, 'value': 'string'})
        zone.add_record(s)

        m = Record.new(
            zone, 'm', {'type': 'M', 'ttl': 43, 'values': ('string', 'another')}
        )
        zone.add_record(m)

        # this should check for the template method on our values that don't
        # have one
        templ.process_source_and_target_zones(zone, None, None)
        # and these should make sure that the value types were asked if they
        # have a template method
        self.assertEqual({'template'}, s.value._asked_for)
        self.assertEqual({'template'}, m.values[0]._asked_for)

    @patch('octodns.record.TxtValue.template')
    def test_trailing_dots(self, mock_template):
        templ = Templating('test', trailing_dots=False)

        zone = Zone('unit.tests.', [])
        record_source = DummySource('record')
        txt = Record.new(
            zone,
            'txt',
            {
                'type': 'TXT',
                'ttl': 42,
                'value': 'There are {zone_num_records} record(s) in {zone_name}.',
            },
            source=record_source,
        )
        zone.add_record(txt)

        templ.process_source_and_target_zones(zone, None, None)
        mock_template.assert_called_once()
        self.assertEqual(
            call(
                {
                    'record_name': 'txt',
                    'record_decoded_name': 'txt',
                    'record_encoded_name': 'txt',
                    'record_fqdn': 'txt.unit.tests',
                    'record_decoded_fqdn': 'txt.unit.tests',
                    'record_encoded_fqdn': 'txt.unit.tests',
                    'record_source_id': 'record',
                    'record_type': 'TXT',
                    'record_ttl': 42,
                    'zone_name': 'unit.tests',
                    'zone_decoded_name': 'unit.tests',
                    'zone_encoded_name': 'unit.tests',
                    'zone_num_records': 1,
                }
            ),
            mock_template.call_args,
        )

    def test_context(self):
        templ = Templating(
            'test',
            context={
                # static
                'the_answer': 42,
                # dynamic
                'the_date': lambda _, __: 'today',
                # uses a param
                'provider': lambda _, pro: pro,
            },
        )

        zone = Zone('unit.tests.', [])
        txt = Record.new(
            zone,
            'txt',
            {
                'type': 'TXT',
                'ttl': 42,
                'values': (
                    'the_answer: {the_answer}',
                    'the_date: {the_date}',
                    'provider: {provider}',
                ),
            },
        )
        zone.add_record(txt)

        got, _ = templ.process_source_and_target_zones(zone, None, 'da-pro')
        txt = _find(got, 'txt')
        self.assertEqual(3, len(txt.values))
        self.assertEqual('provider: da-pro', txt.values[0])
        self.assertEqual('the_answer: 42', txt.values[1])
        self.assertEqual('the_date: today', txt.values[2])

    def test_bad_key(self):
        templ = Templating('test')

        zone = Zone('unit.tests.', [])
        txt = Record.new(
            zone,
            'txt',
            {'type': 'TXT', 'ttl': 42, 'value': 'this {bad} does not exist'},
        )
        zone.add_record(txt)

        with self.assertRaises(TemplatingError) as ctx:
            templ.process_source_and_target_zones(zone, None, None)
        self.assertEqual(
            'Invalid record "txt.unit.tests.", undefined template parameter "bad" in value',
            str(ctx.exception),
        )

        zone = Zone('unit.tests.', [])
        cname = Record.new(
            zone,
            'cname',
            {
                'type': 'CNAME',
                'ttl': 42,
                'value': '_cname.{bad}something.else.',
            },
            lenient=True,
        )
        zone.add_record(cname)

        with self.assertRaises(TemplatingError) as ctx:
            templ.process_source_and_target_zones(zone, None, None)
        self.assertEqual(
            'Invalid record "cname.unit.tests.", undefined template parameter "bad" in value',
            str(ctx.exception),
        )
