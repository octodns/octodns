#
#
#

import warnings
from unittest import TestCase

from octodns.record import Record, ValuesMixin
from octodns.record.a import Ipv4Value
from octodns.record.base import ValueMixin
from octodns.record.caa import CaaValue
from octodns.record.cname import CnameValue
from octodns.record.ds import DsValue
from octodns.record.mx import MxValue
from octodns.record.naptr import NaptrValue
from octodns.record.ns import NsValue
from octodns.record.openpgpkey import OpenpgpkeyValue
from octodns.record.rr import Rr
from octodns.record.srv import SrvValue
from octodns.record.sshfp import SshfpValue
from octodns.record.svcb import SvcbValue
from octodns.record.tlsa import TlsaValue
from octodns.record.uri import UriValue
from octodns.record.urlfwd import UrlfwdValue
from octodns.zone import Zone

# (value instance, expected `to_rrs()`, rdata text to feed `from_rrs()`,
# expected `from_rrs()` result)
CASES = (
    (
        CaaValue({'flags': 1, 'tag': 'tag1', 'value': 'v'}),
        '1 tag1 "v"',
        '1 tag1 "v"',
        {'flags': 1, 'tag': 'tag1', 'value': 'v'},
    ),
    (
        DsValue(
            {
                'key_tag': 1,
                'algorithm': 2,
                'digest_type': 3,
                'digest': '99148c44',
            }
        ),
        '1 2 3 99148c44',
        '1 2 3 99148c44',
        {'key_tag': 1, 'algorithm': 2, 'digest_type': 3, 'digest': '99148c44'},
    ),
    (Ipv4Value('1.2.3.4'), '1.2.3.4', '1.2.3.4', '1.2.3.4'),
    (
        CnameValue('some.target.'),
        'some.target.',
        'some.target.',
        'some.target.',
    ),
    (NsValue('some.target.'), 'some.target.', 'some.target.', 'some.target.'),
    (
        MxValue({'preference': 10, 'exchange': 'mx.unit.tests.'}),
        '10 mx.unit.tests.',
        '10 mx.unit.tests.',
        {'preference': 10, 'exchange': 'mx.unit.tests.'},
    ),
    (
        NaptrValue(
            {
                'order': 1,
                'preference': 2,
                'flags': 'S',
                'service': 'srv',
                'regexp': 're',
                'replacement': '.',
            }
        ),
        '1 2 "S" "srv" "re" .',
        '1 2 "S" "srv" "re" .',
        {
            'order': 1,
            'preference': 2,
            'flags': 'S',
            'service': 'srv',
            'regexp': 're',
            'replacement': '.',
        },
    ),
    (OpenpgpkeyValue('abc123'), 'abc123', 'abc123', 'abc123'),
    (
        SrvValue(
            {'priority': 1, 'weight': 2, 'port': 3, 'target': 'srv.unit.tests.'}
        ),
        '1 2 3 srv.unit.tests.',
        '1 2 3 srv.unit.tests.',
        {'priority': 1, 'weight': 2, 'port': 3, 'target': 'srv.unit.tests.'},
    ),
    (
        SshfpValue(
            {'algorithm': 1, 'fingerprint_type': 2, 'fingerprint': '00479b27'}
        ),
        '1 2 00479b27',
        '1 2 00479b27',
        {'algorithm': 1, 'fingerprint_type': 2, 'fingerprint': '00479b27'},
    ),
    (
        SvcbValue({'svcpriority': 1, 'targetname': 'svcb.unit.tests.'}),
        '1 svcb.unit.tests.',
        '1 svcb.unit.tests.',
        {'svcpriority': 1, 'targetname': 'svcb.unit.tests.', 'svcparams': {}},
    ),
    (
        TlsaValue(
            {
                'certificate_usage': 2,
                'selector': 1,
                'matching_type': 0,
                'certificate_association_data': 'abcd',
            }
        ),
        '2 1 0 abcd',
        '2 1 0 abcd',
        {
            'certificate_usage': 2,
            'selector': 1,
            'matching_type': 0,
            'certificate_association_data': 'abcd',
        },
    ),
    (
        UriValue(
            {'priority': 1, 'weight': 2, 'target': 'ssh://uri.unit.tests./'}
        ),
        '1 2 "ssh://uri.unit.tests./"',
        '1 2 "ssh://uri.unit.tests./"',
        {'priority': 1, 'weight': 2, 'target': 'ssh://uri.unit.tests./'},
    ),
    (
        UrlfwdValue(
            {
                'path': '/',
                'target': 'http://foo/',
                'code': 301,
                'masking': 2,
                'query': 0,
            }
        ),
        '"/" "http://foo/" 301 2 0',
        '"/" "http://foo/" 301 2 0',
        {
            'path': '/',
            'target': 'http://foo/',
            'code': 301,
            'masking': 2,
            'query': 0,
        },
    ),
)


class TestValueToRrs(TestCase):
    def test_to_rrs_matches_rdata_text(self):
        for value, expected, _, _ in CASES:
            cls = value.__class__
            with self.subTest(cls=cls.__name__):
                self.assertEqual(expected, value.to_rrs())

                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    self.assertEqual(expected, value.rdata_text)
                matched = [
                    w
                    for w in caught
                    if issubclass(w.category, DeprecationWarning)
                    and cls.__name__ in str(w.message)
                    and 'rdata_text' in str(w.message)
                    and 'to_rrs' in str(w.message)
                ]
                self.assertTrue(
                    matched, f'{cls.__name__}.rdata_text did not warn'
                )

    def test_from_rrs_matches_parse_rdata_text(self):
        for value, _, rdata, expected in CASES:
            cls = value.__class__
            with self.subTest(cls=cls.__name__):
                self.assertEqual(expected, cls.from_rrs(rdata))

                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    self.assertEqual(expected, cls.parse_rdata_text(rdata))
                matched = [
                    w
                    for w in caught
                    if issubclass(w.category, DeprecationWarning)
                    and cls.__name__ in str(w.message)
                    and 'parse_rdata_text' in str(w.message)
                    and 'from_rrs' in str(w.message)
                ]
                self.assertTrue(
                    matched, f'{cls.__name__}.parse_rdata_text did not warn'
                )


class LegacyValue(str):
    # a stand-in for a 3rd-party value type that has not migrated off the
    # deprecated rdata_text/parse_rdata_text API
    VALIDATORS = []

    @classmethod
    def _schema(cls):
        return {'type': 'string'}

    @classmethod
    def parse_rdata_text(cls, value):
        return cls(value.upper())

    @classmethod
    def process(cls, values):
        return [cls(v) for v in values]

    @property
    def rdata_text(self):
        return str(self).lower()

    def template(self, params):
        return self


class LegacyValuesRecord(ValuesMixin, Record):
    _type = 'LEGACY-VALUE-TEST'
    _value_type = LegacyValue


class LegacySingleValue(LegacyValue):
    @classmethod
    def process(cls, value):
        return cls(value)


class LegacyValueRecord(ValueMixin, Record):
    _type = 'LEGACY-SINGLE-VALUE-TEST'
    _value_type = LegacySingleValue


Record.register_type(LegacyValuesRecord)
Record.register_type(LegacyValueRecord)


class TestLegacyValueFallback(TestCase):
    zone = Zone('unit.tests.', [])

    def test_rrs_falls_back_to_rdata_text(self):
        record = Record.new(
            self.zone,
            'legacy',
            {
                'type': 'LEGACY-VALUE-TEST',
                'ttl': 42,
                'values': ['Hello', 'World'],
            },
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            rrs = record.rrs
        self.assertEqual(
            ('legacy.unit.tests.', 42, 'LEGACY-VALUE-TEST', ['hello', 'world']),
            rrs,
        )
        matched = [
            w
            for w in caught
            if issubclass(w.category, DeprecationWarning)
            and 'LegacyValue' in str(w.message)
            and 'to_rrs' in str(w.message)
        ]
        self.assertTrue(matched)

    def test_data_from_rrs_falls_back_to_parse_rdata_text(self):
        rrs = [Rr('legacy.unit.tests.', 'LEGACY-VALUE-TEST', 42, 'hello')]
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            records = Record.from_rrs(self.zone, rrs)
        self.assertEqual(1, len(records))
        self.assertEqual(['HELLO'], records[0].values)
        matched = [
            w
            for w in caught
            if issubclass(w.category, DeprecationWarning)
            and 'LegacyValue' in str(w.message)
            and 'from_rrs' in str(w.message)
        ]
        self.assertTrue(matched)

    def test_value_mixin_rrs_falls_back_to_rdata_text(self):
        record = Record.new(
            self.zone,
            'legacy-single',
            {'type': 'LEGACY-SINGLE-VALUE-TEST', 'ttl': 42, 'value': 'Hello'},
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            rrs = record.rrs
        self.assertEqual(
            (
                'legacy-single.unit.tests.',
                42,
                'LEGACY-SINGLE-VALUE-TEST',
                ['hello'],
            ),
            rrs,
        )
        matched = [
            w
            for w in caught
            if issubclass(w.category, DeprecationWarning)
            and 'LegacySingleValue' in str(w.message)
            and 'to_rrs' in str(w.message)
        ]
        self.assertTrue(matched)
