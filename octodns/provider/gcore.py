#
#
#

from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from collections import defaultdict
from requests import Session
import logging

from ..record import Record
from .base import BaseProvider


class GCoreClientException(Exception):
    def __init__(self, r):
        super(GCoreClientException, self).__init__(r.text)


class GCoreClientBadRequest(GCoreClientException):
    def __init__(self, r):
        super(GCoreClientBadRequest, self).__init__(r)


class GCoreClientNotFound(GCoreClientException):
    def __init__(self, r):
        super(GCoreClientNotFound, self).__init__(r)


class GCoreClient(object):

    ROOT_ZONES = "/zones"

    def __init__(self, base_url, token):
        session = Session()
        session.headers.update({"Authorization": "Bearer {}".format(token)})
        self._session = session
        self._base_url = base_url

    def _request(self, method, path, params={}, data=None):
        url = "{}{}".format(self._base_url, path)
        r = self._session.request(
            method, url, params=params, json=data, timeout=30.0
        )
        if r.status_code == 400:
            raise GCoreClientBadRequest(r)
        elif r.status_code == 404:
            raise GCoreClientNotFound(r)
        elif r.status_code == 500:
            raise GCoreClientException(r)
        r.raise_for_status()
        return r

    def zone(self, zone_name):
        return self._request(
            "GET", "{}/{}".format(self.ROOT_ZONES, zone_name)
        ).json()

    def zone_create(self, zone_name):
        return self._request(
            "POST", self.ROOT_ZONES, data={"name": zone_name}
        ).json()

    def zone_records(self, zone_name):
        rrsets = self._request(
            "GET", "{}/{}/rrsets".format(self.ROOT_ZONES, zone_name)
        ).json()
        records = rrsets["rrsets"]
        return records

    def record_create(self, zone_name, rrset_name, type_, data):
        self._request(
            "POST", self._rrset_url(zone_name, rrset_name, type_), data=data
        )

    def record_update(self, zone_name, rrset_name, type_, data):
        self._request(
            "PUT", self._rrset_url(zone_name, rrset_name, type_), data=data
        )

    def record_delete(self, zone_name, rrset_name, type_):
        self._request("DELETE", self._rrset_url(zone_name, rrset_name, type_))

    def _rrset_url(self, zone_name, rrset_name, type_):
        return "{}/{}/{}/{}".format(
            self.ROOT_ZONES, zone_name, rrset_name, type_
        )


class GCoreProvider(BaseProvider):
    """
    GCore provider using API v2.

    gcore:
        class: octodns.provider.gcore.GCoreProvider
        # Your API key (required)
        token: XXXXXXXXXXXX
        # url: https://dnsapi.gcorelabs.com/v2
    """

    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS = set(("A", "AAAA"))

    def __init__(self, id, token, *args, **kwargs):
        base_url = kwargs.pop("url", "https://dnsapi.gcorelabs.com/v2")
        self.log = logging.getLogger("GCoreProvider[{}]".format(id))
        self.log.debug("__init__: id=%s, token=***", id)
        super(GCoreProvider, self).__init__(id, *args, **kwargs)
        self._client = GCoreClient(base_url, token)

    def _data_for_single(self, _type, record):
        return {
            "ttl": record["ttl"],
            "type": _type,
            "values": record["resource_records"][0]["content"],
        }

    _data_for_A = _data_for_single
    _data_for_AAAA = _data_for_single

    def zone_records(self, zone):
        try:
            return self._client.zone_records(zone.name[:-1]), True
        except GCoreClientNotFound:
            return [], False

    def populate(self, zone, target=False, lenient=False):
        self.log.debug(
            "populate: name=%s, target=%s, lenient=%s",
            zone.name,
            target,
            lenient,
        )

        values = defaultdict(defaultdict)
        records, exists = self.zone_records(zone)
        for record in records:
            _type = record["type"]
            if _type not in self.SUPPORTS:
                continue
            rr_name = record["name"].replace(zone.name, "")
            if len(rr_name) > 0 and rr_name.endswith("."):
                rr_name = rr_name[:-1]
            values[rr_name][_type] = record

        before = len(zone.records)
        for name, types in values.items():
            for _type, record in types.items():
                data_for = getattr(self, "_data_for_{}".format(_type))
                record = Record.new(
                    zone,
                    name,
                    data_for(_type, record),
                    source=self,
                    lenient=lenient,
                )
                zone.add_record(record, lenient=lenient)

        self.log.info(
            "populate:   found %s records, exists=%s",
            len(zone.records) - before,
            exists,
        )
        return exists

    def _params_for_single(self, record):
        return {
            "ttl": record.ttl,
            "resource_records": [{"content": record.values}],
        }

    _params_for_A = _params_for_single
    _params_for_AAAA = _params_for_single

    def _apply_create(self, change):
        new = change.new
        rrset_name = self._build_rrset_name(new)
        data = getattr(self, "_params_for_{}".format(new._type))(new)
        self._client.record_create(
            new.zone.name[:-1], rrset_name, new._type, data
        )

    def _apply_update(self, change):
        new = change.new
        rrset_name = self._build_rrset_name(new)
        data = getattr(self, "_params_for_{}".format(new._type))(new)
        self._client.record_update(
            new.zone.name[:-1], rrset_name, new._type, data
        )

    def _apply_delete(self, change):
        existing = change.existing
        rrset_name = self._build_rrset_name(existing)
        self._client.record_delete(
            existing.zone.name[:-1], rrset_name, existing._type
        )

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        zone = desired.name[:-1]
        self.log.debug(
            "_apply: zone=%s, len(changes)=%d", desired.name, len(changes)
        )

        try:
            self._client.zone(zone)
        except GCoreClientNotFound:
            self.log.info("_apply: no existing zone, trying to create it")
            self._client.zone_create(zone)
            self.log.info("_apply: zone has been successfully created")

        changes.reverse()

        for change in changes:
            class_name = change.__class__.__name__
            getattr(self, "_apply_{}".format(class_name.lower()))(change)

    @staticmethod
    def _build_rrset_name(record):
        if len(record.name) > 0:
            return "{}.{}".format(record.name, record.zone.name)
        return record.zone.name
