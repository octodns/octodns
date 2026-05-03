#
#
#

from unittest import TestCase

from octodns.record.alias import AliasRecord
from octodns.record.target import (
    TargetsValueBestPracticeValidator,
    TargetValueBestPracticeValidator,
    _TargetsValue,
    _TargetValue,
)
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


class TestTargetBestPracticeValidators(TestCase):

    def test_target_value_best_practice_validator(self):
        validate = TargetValueBestPracticeValidator(
            'target-value-best-practice'
        ).validate

        # valid: trailing dot present
        self.assertEqual([], validate(_TargetValue, 'foo.bar.com.', 'CNAME'))

        # missing/empty value — no error (format validator handles that)
        self.assertEqual([], validate(_TargetValue, None, 'CNAME'))
        self.assertEqual([], validate(_TargetValue, '', 'CNAME'))

        # null target for permitted types — exempt
        self.assertEqual([], validate(_TargetValue, '.', 'SRV'))

        # template variable — exempt until after substitution
        self.assertEqual(
            [], validate(_TargetValue, '{zone_name}example.com', 'CNAME')
        )

        # missing trailing dot
        self.assertEqual(
            ['CNAME value "foo.bar.com" missing trailing .'],
            validate(_TargetValue, 'foo.bar.com', 'CNAME'),
        )

    def test_targets_value_best_practice_validator(self):
        validate = TargetsValueBestPracticeValidator(
            'targets-value-best-practice'
        ).validate

        # valid
        self.assertEqual(
            [], validate(_TargetsValue, ['ns1.foo.com.', 'ns2.foo.com.'], 'NS')
        )

        # empty list — no errors
        self.assertEqual([], validate(_TargetsValue, [], 'NS'))

        # template variable — exempt
        self.assertEqual([], validate(_TargetsValue, ['{zone_name}ns1'], 'NS'))

        # missing trailing dot
        self.assertEqual(
            ['NS value "foo.bar" missing trailing .'],
            validate(_TargetsValue, ['foo.bar'], 'NS'),
        )

        # multiple values, one bad
        self.assertEqual(
            ['NS value "ns2.foo.com" missing trailing .'],
            validate(_TargetsValue, ['ns1.foo.com.', 'ns2.foo.com'], 'NS'),
        )
