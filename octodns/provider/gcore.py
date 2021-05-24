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
import http
import logging
import urllib.parse

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

    ROOT_ZONES = "zones"

    def __init__(
        self,
        log,
        api_url,
        auth_url,
        token=None,
        token_type=None,
        login=None,
        password=None,
    ):
        self.log = log
        self._session = Session()
        self._api_url = api_url
        if token is not None and token_type is not None:
            self._session.headers.update(
                {"Authorization": "{} {}".format(token_type, token)}
            )
        elif login is not None and password is not None:
            token = self._auth(auth_url, login, password)
            self._session.headers.update(
                {"Authorization": "Bearer {}".format(token)}
            )
        else:
            raise ValueError("either token or login & password must be set")

    def _auth(self, url, login, password):
        # well, can't use _request, since API returns 400 if credentials
        # invalid which will be logged, but we don't want do this
        r = self._session.request(
            "POST",
            self._build_url(url, "auth", "jwt", "login"),
            json={"username": login, "password": password},
        )
        r.raise_for_status()
        return r.json()["access"]

    def _request(self, method, url, params=None, data=None):
        r = self._session.request(
            method, url, params=params, json=data, timeout=30.0
        )
        if r.status_code == http.HTTPStatus.BAD_REQUEST:
            self.log.error(
                "bad request %r has been sent to %r: %s", data, url, r.text
            )
            raise GCoreClientBadRequest(r)
        elif r.status_code == http.HTTPStatus.NOT_FOUND:
            self.log.error("resource %r not found: %s", url, r.text)
            raise GCoreClientNotFound(r)
        elif r.status_code == http.HTTPStatus.INTERNAL_SERVER_ERROR:
            self.log.error("server error no %r to %r: %s", data, url, r.text)
            raise GCoreClientException(r)
        r.raise_for_status()
        return r

    def zone(self, zone_name):
        return self._request(
            "GET", self._build_url(self._api_url, self.ROOT_ZONES, zone_name)
        ).json()

    def zone_create(self, zone_name):
        return self._request(
            "POST",
            self._build_url(self._api_url, self.ROOT_ZONES),
            data={"name": zone_name},
        ).json()

    def zone_records(self, zone_name):
        rrsets = self._request(
            "GET",
            "{}".format(
                self._build_url(
                    self._api_url, self.ROOT_ZONES, zone_name, "rrsets"
                )
            ),
            params={"all": "true"},
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
        return self._build_url(
            self._api_url, self.ROOT_ZONES, zone_name, rrset_name, type_
        )

    @staticmethod
    def _build_url(base, *items):
        for i in items:
            base = base.strip("/") + "/"
            base = urllib.parse.urljoin(base, i)
        return base


class GCoreProvider(BaseProvider):
    """
    GCore provider using API v2.

    gcore:
        class: octodns.provider.gcore.GCoreProvider
        # Your API key
        token: XXXXXXXXXXXX
        # token_type: APIKey
        # or login + password
        login: XXXXXXXXXXXX
        password: XXXXXXXXXXXX
        # auth_url: https://api.gcdn.co
        # url: https://dnsapi.gcorelabs.com/v2
    """

    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS = set(("A", "AAAA"))

    def __init__(self, id, *args, **kwargs):
        token = kwargs.pop("token", None)
        token_type = kwargs.pop("token_type", "APIKey")
        login = kwargs.pop("login", None)
        password = kwargs.pop("password", None)
        api_url = kwargs.pop("url", "https://dnsapi.gcorelabs.com/v2")
        auth_url = kwargs.pop("auth_url", "https://api.gcdn.co")
        self.log = logging.getLogger("GCoreProvider[{}]".format(id))
        self.log.debug("__init__: id=%s", id)
        super(GCoreProvider, self).__init__(id, *args, **kwargs)
        self._client = GCoreClient(
            self.log,
            api_url,
            auth_url,
            token=token,
            token_type=token_type,
            login=login,
            password=password,
        )

    def _data_for_single(self, _type, record):
        return {
            "ttl": record["ttl"],
            "type": _type,
            "values": [
                rr_value
                for resource_record in record["resource_records"]
                for rr_value in resource_record["content"]
            ],
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
            _type = record["type"].upper()
            if _type not in self.SUPPORTS:
                continue
            rr_name = zone.hostname_from_fqdn(record["name"])
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
            "resource_records": [
                {"content": [value]} for value in record.values
            ],
        }

    _params_for_A = _params_for_single
    _params_for_AAAA = _params_for_single

    def _apply_create(self, change):
        self.log.info("creating: %s", change)
        new = change.new
        data = getattr(self, "_params_for_{}".format(new._type))(new)
        self._client.record_create(
            new.zone.name[:-1], new.fqdn, new._type, data
        )

    def _apply_update(self, change):
        self.log.info("updating: %s", change)
        new = change.new
        data = getattr(self, "_params_for_{}".format(new._type))(new)
        self._client.record_update(
            new.zone.name[:-1], new.fqdn, new._type, data
        )

    def _apply_delete(self, change):
        self.log.info("deleting: %s", change)
        existing = change.existing
        self._client.record_delete(
            existing.zone.name[:-1], existing.fqdn, existing._type
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
