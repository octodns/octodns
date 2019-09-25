#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

# from mock import Mock, call
from os.path import dirname, join

from suds import WebFault

from requests_mock import ANY, mock as requests_mock
from unittest import TestCase

from octodns.record import Record
from octodns.provider.transip import TransipProvider
from octodns.provider.yaml import YamlProvider
from octodns.zone import Zone
from transip.service.domain import DomainService
from transip.service.objects import DnsEntry




class MockDomainService(DomainService):

    def __init__(self, *args, **kwargs):
        super(MockDomainService, self).__init__('MockDomainService', *args, **kwargs)
        self.mockupEntries = []

    def mockup(self, records):

        provider = TransipProvider('', '', '');

        _dns_entries = []
        for record in records:
            if record._type in provider.SUPPORTS:
                entries_for = getattr(provider, '_entries_for_{}'.format(record._type))

                # Root records have '@' as name
                name = record.name
                if name == '':
                    name = provider.ROOT_RECORD

                _dns_entries.extend(entries_for(name, record))

                _dns_entries.append(DnsEntry('@', '3600', 'NS', 'ns01.transip.nl.'))


        self.mockupEntries = _dns_entries

    # Skips authentication layer and returns the entries loaded by "Mockup"
    def get_info(self, domain_name):

        if str(domain_name) == str('notfound.unit.tests'):
            self.raiseZoneNotFound()

        result = lambda: None
        setattr(result, "dnsEntries", self.mockupEntries)
        return result

    def set_dns_entries(self, domain_name, dns_entries):
        if str(domain_name) == str('failsetdns.unit.tests'):
            self.raiseSaveError()

        return True

    def raiseZoneNotFound(self):
        fault = lambda: None
        setattr(fault, "faultstring", '102 is zone not found')
        setattr(fault, "faultcode", str('102'))
        document = {}
        raise WebFault(fault, document)

    def raiseInvalidAuth(self):
        fault = lambda: None
        setattr(fault, "faultstring", '200 is invalid auth')
        setattr(fault, "faultcode", str('200'))
        document = {}
        raise WebFault(fault, document)

    def raiseSaveError(self):
        fault = lambda: None
        setattr(fault, "faultstring", '202 error while saving')
        setattr(fault, "faultcode", str('202'))
        document = {}
        raise WebFault(fault, document)



class TestTransipProvider(TestCase):
    bogus_key = str("""-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA0U5HGCkLrz423IyUf3u4cKN2WrNz1x5KNr6PvH2M/zxas+zB
elbxkdT3AQ+wmfcIvOuTmFRTHv35q2um1aBrPxVw+2s+lWo28VwIRttwIB1vIeWu
lSBnkEZQRLyPI2tH0i5QoMX4CVPf9rvij3Uslimi84jdzDfPFIh6jZ6C8nLipOTG
0IMhge1ofVfB0oSy5H+7PYS2858QLAf5ruYbzbAxZRivS402wGmQ0d0Lc1KxraAj
kiMM5yj/CkH/Vm2w9I6+tLFeASE4ub5HCP5G/ig4dbYtqZMQMpqyAbGxd5SOVtyn
UHagAJUxf8DT3I8PyjEHjxdOPUsxNyRtepO/7QIDAQABAoIBAQC7fiZ7gxE/ezjD
2n6PsHFpHVTBLS2gzzZl0dCKZeFvJk6ODJDImaeuHhrh7X8ifMNsEI9XjnojMhl8
MGPzy88mZHugDNK0H8B19x5G8v1/Fz7dG5WHas660/HFkS+b59cfdXOugYiOOn9O
08HBBpLZNRUOmVUuQfQTjapSwGLG8PocgpyRD4zx0LnldnJcqYCxwCdev+AAsPnq
ibNtOd/MYD37w9MEGcaxLE8wGgkv8yd97aTjkgE+tp4zsM4QE4Rag133tsLLNznT
4Qr/of15M3NW/DXq/fgctyRcJjZpU66eCXLCz2iRTnLyyxxDC2nwlxKbubV+lcS0
S4hbfd/BAoGBAO8jXxEaiybR0aIhhSR5esEc3ymo8R8vBN3ZMJ+vr5jEPXr/ZuFj
/R4cZ2XV3VoQJG0pvIOYVPZ5DpJM7W+zSXtJ/7bLXy4Bnmh/rc+YYgC+AXQoLSil
iD2OuB2xAzRAK71DVSO0kv8gEEXCersPT2i6+vC2GIlJvLcYbOdRKWGxAoGBAOAQ
aJbRLtKujH+kMdoMI7tRlL8XwI+SZf0FcieEu//nFyerTePUhVgEtcE+7eQ7hyhG
fIXUFx/wALySoqFzdJDLc8U8pTLhbUaoLOTjkwnCTKQVprhnISqQqqh/0U5u47IE
RWzWKN6OHb0CezNTq80Dr6HoxmPCnJHBHn5LinT9AoGAQSpvZpbIIqz8pmTiBl2A
QQ2gFpcuFeRXPClKYcmbXVLkuhbNL1BzEniFCLAt4LQTaRf9ghLJ3FyCxwVlkpHV
zV4N6/8hkcTpKOraL38D/dXJSaEFJVVuee/hZl3tVJjEEpA9rDwx7ooLRSdJEJ6M
ciq55UyKBSdt4KssSiDI2RECgYBL3mJ7xuLy5bWfNsrGiVvD/rC+L928/5ZXIXPw
26oI0Yfun7ulDH4GOroMcDF/GYT/Zzac3h7iapLlR0WYI47xxGI0A//wBZLJ3QIu
krxkDo2C9e3Y/NqnHgsbOQR3aWbiDT4wxydZjIeXS3LKA2fl6Hyc90PN3cTEOb8I
hq2gRQKBgEt0SxhhtyB93SjgTzmUZZ7PiEf0YJatfM6cevmjWHexrZH+x31PB72s
fH2BQyTKKzoCLB1k/6HRaMnZdrWyWSZ7JKz3AHJ8+58d0Hr8LTrzDM1L6BbjeDct
N4OiVz1I3rbZGYa396lpxO6ku8yCglisL1yrSP6DdEUp66ntpKVd
-----END RSA PRIVATE KEY-----""")


    def make_expected(self):
        expected = Zone('unit.tests.', [])
        source = YamlProvider('test', join(dirname(__file__), 'config'))
        source.populate(expected)
        return expected

    def test_populate(self):

        _expected = self.make_expected()

        with self.assertRaises(WebFault) as ctx:
            provider = TransipProvider('test', 'unittest', self.bogus_key)
            zone = Zone('unit.tests.', [])
            provider.populate(zone, True)

        self.assertEquals(str('WebFault'),
                          str(ctx.exception.__class__.__name__))

        self.assertEquals(str('200'), ctx.exception.fault.faultcode)

        with self.assertRaises(Exception) as ctx:
            provider = TransipProvider('test', 'unittest', self.bogus_key)
            provider._client = MockDomainService('unittest', self.bogus_key)
            zone = Zone('notfound.unit.tests.', [])
            provider.populate(zone, True)

        self.assertEquals(str('Exception'),
                          str(ctx.exception.__class__.__name__))

        self.assertEquals('populate: (102) Transip used as target for non-existing zone: notfound.unit.tests.', ctx.exception.message)

        provider = TransipProvider('test', 'unittest', self.bogus_key)
        provider._client = MockDomainService('unittest', self.bogus_key)
        zone = Zone('notfound.unit.tests.', [])
        provider.populate(zone, False)

        provider = TransipProvider('test', 'unittest', self.bogus_key)
        provider._client = MockDomainService('unittest', self.bogus_key)
        provider._client.mockup(_expected.records)
        zone = Zone('unit.tests.', [])
        provider.populate(zone, False)

        provider._currentZone = zone
        self.assertEquals("www.unit.tests.", provider._parse_to_fqdn("www"))


        provider = TransipProvider('test', 'unittest', self.bogus_key)
        provider._client = MockDomainService('unittest', self.bogus_key)
        zone = Zone('unit.tests.', [])
        exists = provider.populate(zone, True)
        self.assertTrue(exists, 'populate should return true')


        return

    def test_plan(self):

        _expected = self.make_expected()

        print(_expected.name)

        provider = TransipProvider('test', 'unittest', self.bogus_key)
        provider._client = MockDomainService('unittest', self.bogus_key)
        plan = provider.plan(_expected)

        self.assertEqual(12, plan.change_counts['Create'])
        self.assertEqual(0, plan.change_counts['Update'])
        self.assertEqual(0, plan.change_counts['Delete'])

        return

    def test_apply(self):

        _expected = self.make_expected()

        provider = TransipProvider('test', 'unittest', self.bogus_key)
        provider._client = MockDomainService('unittest', self.bogus_key)
        plan = provider.plan(_expected)
        #self.assertEqual(11, plan.changes)
        changes = provider.apply(plan)



        with self.assertRaises(Exception) as ctx:
            provider = TransipProvider('test', 'unittest', self.bogus_key)
            provider._client = MockDomainService('unittest', self.bogus_key)
            plan = provider.plan(_expected)
            plan.desired.name = 'notfound.unit.tests.'
            changes = provider.apply(plan)
            # self.assertEqual(11, changes)

        self.assertEquals(str('WebFault'),
                          str(ctx.exception.__class__.__name__))

        _expected = self.make_expected()

        with self.assertRaises(Exception) as ctx:
            provider = TransipProvider('test', 'unittest', self.bogus_key)
            provider._client = MockDomainService('unittest', self.bogus_key)
            plan = provider.plan(_expected)
            plan.desired.name = 'failsetdns.unit.tests.'
            changes = provider.apply(plan)
            # self.assertEqual(11, changes)


        #provider = TransipProvider('test', 'unittest', self.bogus_key)

        #plan = provider.plan(_expected)

#        changes = provider.apply(plan)
#        self.assertEquals(29, changes)


