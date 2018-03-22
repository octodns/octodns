#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from StringIO import StringIO
from logging import getLogger
from unittest import TestCase

from octodns.provider.plan import Plan, PlanHtml, PlanLogger, PlanMarkdown
from octodns.record import Create, Delete, Record, Update
from octodns.zone import Zone

from helpers import SimpleProvider


simple = SimpleProvider()
zone = Zone('unit.tests.', [])
existing = Record.new(zone, 'a', {
    'ttl': 300,
    'type': 'A',
    # This matches the zone data above, one to swap, one to leave
    'values': ['1.1.1.1', '2.2.2.2'],
})
new = Record.new(zone, 'a', {
    'geo': {
        'AF': ['5.5.5.5'],
        'NA-US': ['6.6.6.6']
    },
    'ttl': 300,
    'type': 'A',
    # This leaves one, swaps ones, and adds one
    'values': ['2.2.2.2', '3.3.3.3', '4.4.4.4'],
}, simple)
create = Create(Record.new(zone, 'b', {
    'ttl': 60,
    'type': 'CNAME',
    'value': 'foo.unit.tests.'
}, simple))
create2 = Create(Record.new(zone, 'c', {
    'ttl': 60,
    'type': 'CNAME',
    'value': 'foo.unit.tests.'
}))
update = Update(existing, new)
delete = Delete(new)
changes = [create, create2, delete, update]
plans = [
    (simple, Plan(zone, zone, changes, True)),
    (simple, Plan(zone, zone, changes, False)),
]


class TestPlanLogger(TestCase):

    def test_invalid_level(self):
        with self.assertRaises(Exception) as ctx:
            PlanLogger('invalid', 'not-a-level')
        self.assertEquals('Unsupported level: not-a-level',
                          ctx.exception.message)

    def test_create(self):

        class MockLogger(object):

            def __init__(self):
                self.out = StringIO()

            def log(self, level, msg):
                self.out.write(msg)

        log = MockLogger()
        PlanLogger('logger').run(log, plans)
        out = log.out.getvalue()
        self.assertTrue('Summary: Creates=2, Updates=1, '
                        'Deletes=1, Existing Records=0' in out)


class TestPlanHtml(TestCase):
    log = getLogger('TestPlanHtml')

    def test_empty(self):
        out = StringIO()
        PlanHtml('html').run([], fh=out)
        self.assertEquals('<b>No changes were planned</b>', out.getvalue())

    def test_simple(self):
        out = StringIO()
        PlanHtml('html').run(plans, fh=out)
        out = out.getvalue()
        self.assertTrue('    <td colspan=6>Summary: Creates=2, Updates=1, '
                        'Deletes=1, Existing Records=0</td>' in out)


class TestPlanMarkdown(TestCase):
    log = getLogger('TestPlanMarkdown')

    def test_empty(self):
        out = StringIO()
        PlanMarkdown('markdown').run([], fh=out)
        self.assertEquals('## No changes were planned\n', out.getvalue())

    def test_simple(self):
        out = StringIO()
        PlanMarkdown('markdown').run(plans, fh=out)
        out = out.getvalue()
        self.assertTrue('## unit.tests.' in out)
        self.assertTrue('Create | b | CNAME | 60 | foo.unit.tests.' in out)
        self.assertTrue('Update | a | A | 300 | 1.1.1.1;' in out)
        self.assertTrue('NA-US: 6.6.6.6 | test' in out)
        self.assertTrue('Delete | a | A | 300 | 2.2.2.2;' in out)
