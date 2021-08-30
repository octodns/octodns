from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from collections import defaultdict, namedtuple
from logging import getLogger

from transip import TransIP
from transip.exceptions import TransIPHTTPError
from transip.v6.objects import DnsEntry

from ..record import Record
from .base import BaseProvider

DNSEntry = namedtuple("DNSEntry", ("name", "expire", "type", "content"))


class TransipException(Exception):
    pass


class TransipConfigException(TransipException):
    pass


class TransipNewZoneException(TransipException):
    pass


class TransipProvider(BaseProvider):
    """
    Transip DNS provider

    transip:
        class: octodns.provider.transip.TransipProvider
        # Your Transip account name (required)
        account: yourname
        # Path to a private key file (required if key is not used)
        key_file: /path/to/file
        # The api key as string (required if key_file is not used)
        key: |
            '''
            -----BEGIN PRIVATE KEY-----
            ...
            -----END PRIVATE KEY-----
            '''
        # if both `key_file` and `key` are presented `key_file` is used

    """

    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS = set(
        ("A", "AAAA", "CNAME", "MX", "NS", "SRV", "SPF", "TXT", "SSHFP", "CAA")
    )
    # unsupported by OctoDNS: 'TLSA'
    MIN_TTL = 120
    TIMEOUT = 15
    ROOT_RECORD = "@"

    def __init__(self, id, account, key=None, key_file=None, *args, **kwargs):
        self.log = getLogger("TransipProvider[{}]".format(id))
        self.log.debug("__init__: id=%s, account=%s, token=***", id, account)
        super(TransipProvider, self).__init__(id, *args, **kwargs)

        if key_file is not None:
            self._client = TransIP(login=account, private_key_file=key_file)
        elif key is not None:
            self._client = TransIP(login=account, private_key=key)
        else:
            raise TransipConfigException(
                "Missing `key` of `key_file` parameter in config"
            )

        self._currentZone = {}  # TODO: Remove

    def populate(self, zone, target=False, lenient=False):
        """
        Populate the zone with records in-place.
        """
        self._currentZone = zone
        self.log.debug(
            "populate: name=%s, target=%s, lenient=%s",
            zone.name,
            target,
            lenient,
        )

        before = len(zone.records)

        try:
            domain = self._client.domains.get(zone.name.strip("."))
            records = domain.dns.list()
        except TransIPHTTPError as e:
            if e.response_code == 404 and target is False:
                # Zone not found in account, and not a target so just
                # leave an empty zone.
                return False
            elif e.response_code == 404 and target is True:
                self.log.warning("populate: Transip can't create new zones")
                raise TransipNewZoneException(
                    (
                        "populate: ({}) Transip used as target for "
                        "non-existing zone: {}"
                    ).format(e.response_code, zone.name)
                )
            else:
                self.log.error(
                    "populate: (%s) %s ", e.response_code, e.message
                )
                raise TransipException(
                    "Unhandled error: ({}) {}".format(
                        e.response_code, e.message
                    )
                )

        self.log.debug(
            "populate: found %s records for zone %s", len(records), zone.name
        )
        if records:
            values = defaultdict(lambda: defaultdict(list))
            for record in records:
                name = zone.hostname_from_fqdn(record.name)
                if name == self.ROOT_RECORD:
                    name = ""

                if record.type in self.SUPPORTS:
                    values[name][record.type].append(record)

            for name, types in values.items():
                for _type, records in types.items():
                    data_for = getattr(self, "_data_for_{}".format(_type))
                    record = Record.new(
                        zone,
                        name,
                        data_for(_type, records),
                        source=self,
                        lenient=lenient,
                    )
                    zone.add_record(record, lenient=lenient)
        self.log.info(
            "populate: found %s records, exists = true",
            len(zone.records) - before,
        )

        self._currentZone = {}
        return True

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        self.log.debug(
            "apply: zone=%s, changes=%d", desired.name, len(changes)
        )

        self._currentZone = plan.desired
        try:
            domain = self._client.domains.get(plan.desired.name[:-1])
        except TransIPHTTPError as e:
            self.log.exception("_apply: getting the domain failed")
            raise TransipException(
                "Unhandled error: ({}) {}".format(e.response_code, e.message)
            )

        records = []
        for record in plan.desired.records:
            if record._type in self.SUPPORTS:
                entries_for = getattr(
                    self, "_entries_for_{}".format(record._type)
                )

                # Root records have '@' as name
                name = record.name
                if name == "":
                    name = self.ROOT_RECORD

                records.extend(entries_for(name, record))

        # Transform DNSEntry namedtuples into transip.v6.objects.DnsEntry
        # objects, which is a bit ugly because it's quite a magical object.
        api_records = [DnsEntry(domain.dns, r._asdict()) for r in records]
        try:
            domain.dns.replace(api_records)
        except TransIPHTTPError as e:
            self.log.warning(
                "_apply: Set DNS returned one or more errors: {}".format(e)
            )
            raise TransipException(
                "Unhandled error: ({}) {}".format(e.response_code, e.message)
            )

        self._currentZone = {}

    @classmethod
    def _entries_for_multiple(cls, name, record):
        _entries = []

        for value in record.values:
            _entries.append(DNSEntry(name, record.ttl, record._type, value))

        return _entries

    @classmethod
    def _entries_for_single(cls, name, record):

        return [DNSEntry(name, record.ttl, record._type, record.value)]

    _entries_for_A = _entries_for_multiple
    _entries_for_AAAA = _entries_for_multiple
    _entries_for_NS = _entries_for_multiple
    _entries_for_SPF = _entries_for_multiple
    _entries_for_CNAME = _entries_for_single

    @classmethod
    def _entries_for_MX(cls, name, record):
        _entries = []

        for value in record.values:
            content = "{} {}".format(value.preference, value.exchange)
            _entries.append(DNSEntry(name, record.ttl, record._type, content))

        return _entries

    @classmethod
    def _entries_for_SRV(cls, name, record):
        _entries = []

        for value in record.values:
            content = "{} {} {} {}".format(
                value.priority, value.weight, value.port, value.target
            )
            _entries.append(DNSEntry(name, record.ttl, record._type, content))

        return _entries

    @classmethod
    def _entries_for_SSHFP(cls, name, record):
        _entries = []

        for value in record.values:
            content = "{} {} {}".format(
                value.algorithm, value.fingerprint_type, value.fingerprint
            )
            _entries.append(DNSEntry(name, record.ttl, record._type, content))

        return _entries

    @classmethod
    def _entries_for_CAA(cls, name, record):
        _entries = []

        for value in record.values:
            content = "{} {} {}".format(value.flags, value.tag, value.value)
            _entries.append(DNSEntry(name, record.ttl, record._type, content))

        return _entries

    @classmethod
    def _entries_for_TXT(cls, name, record):
        _entries = []

        for value in record.values:
            value = value.replace("\\;", ";")
            _entries.append(DNSEntry(name, record.ttl, record._type, value))

        return _entries

    def _data_for_multiple(self, _type, records):

        _values = []
        for record in records:
            _values.append(record.content)

        return {
            "ttl": _get_lowest_ttl(records),
            "type": _type,
            "values": _values,
        }

    _data_for_A = _data_for_multiple
    _data_for_AAAA = _data_for_multiple
    _data_for_NS = _data_for_multiple
    _data_for_SPF = _data_for_multiple

    def _data_for_CNAME(self, _type, records):
        return {
            "ttl": records[0].expire,
            "type": _type,
            "value": parse_to_fqdn(records[0].content, self._currentZone),
        }

    def _data_for_MX(self, _type, records):
        _values = []
        for record in records:
            preference, exchange = record.content.split(" ", 1)
            _values.append(
                {
                    "preference": preference,
                    "exchange": parse_to_fqdn(exchange, self._currentZone),
                }
            )
        return {
            "ttl": _get_lowest_ttl(records),
            "type": _type,
            "values": _values,
        }

    def _data_for_SRV(self, _type, records):
        _values = []
        for record in records:
            priority, weight, port, target = record.content.split(" ", 3)
            _values.append(
                {
                    "port": port,
                    "priority": priority,
                    "target": parse_to_fqdn(target, self._currentZone),
                    "weight": weight,
                }
            )

        return {
            "type": _type,
            "ttl": _get_lowest_ttl(records),
            "values": _values,
        }

    def _data_for_SSHFP(self, _type, records):
        _values = []
        for record in records:
            algorithm, fp_type, fingerprint = record.content.split(" ", 2)
            _values.append(
                {
                    "algorithm": algorithm,
                    "fingerprint": fingerprint.lower(),
                    "fingerprint_type": fp_type,
                }
            )

        return {
            "type": _type,
            "ttl": _get_lowest_ttl(records),
            "values": _values,
        }

    def _data_for_CAA(self, _type, records):
        _values = []
        for record in records:
            flags, tag, value = record.content.split(" ", 2)
            _values.append({"flags": flags, "tag": tag, "value": value})

        return {
            "type": _type,
            "ttl": _get_lowest_ttl(records),
            "values": _values,
        }

    def _data_for_TXT(self, _type, records):
        _values = []
        for record in records:
            _values.append(record.content.replace(";", "\\;"))

        return {
            "type": _type,
            "ttl": _get_lowest_ttl(records),
            "values": _values,
        }


def parse_to_fqdn(value, current_zone):
    # TransIP allows '@' as value to alias the root record.
    # this provider won't set an '@' value, but can be an existing record
    if value == TransipProvider.ROOT_RECORD:
        value = current_zone.name

    if value[-1] != ".":
        value = "{}.{}".format(value, current_zone.name)

    return value

def _get_lowest_ttl(records):
    return min([r.expire for r in records] + [100000])
