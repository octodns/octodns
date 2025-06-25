#
#
#

from unittest import TestCase

from octodns.record.alias import AliasRecord
from octodns.record.target import _TargetsValue, _TargetValue
from octodns.zone import Zone


class TestRecordTarget(TestCase):
    def test_target_rdata_text(self):
        # anything goes, we're a noop
        for s in (
            None,
            '',
            'word',
            42,
            42.43,
            '1.2.3',
            'some.words.that.here',
            '1.2.word.4',
            '1.2.3.4',
        ):
            self.assertEqual(s, _TargetValue.parse_rdata_text(s))

        zone = Zone('unit.tests.', [])
        a = AliasRecord(zone, 'a', {'ttl': 42, 'value': 'some.target.'})
        self.assertEqual('some.target.', a.value.rdata_text)


class TestTargetValue(TestCase):

    def test_template(self):
        s = 'this.has.no.templating.'
        value = _TargetValue(s)
        got = value.template({'needle': 42})
        self.assertIs(value, got)

        s = 'this.does.{needle}.have.templating.'
        value = _TargetValue(s)
        got = value.template({'needle': 42})
        self.assertIsNot(value, got)
        self.assertEqual('this.does.42.have.templating.', got)


class TestTargetsValue(TestCase):

    def test_template(self):
        s = 'this.has.no.templating.'
        value = _TargetsValue(s)
        got = value.template({'needle': 42})
        self.assertIs(value, got)

        s = 'this.does.{needle}.have.templating.'
        value = _TargetsValue(s)
        got = value.template({'needle': 42})
        self.assertIsNot(value, got)
        self.assertEqual('this.does.42.have.templating.', got)
