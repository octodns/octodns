#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

import shlex
import time
from logging import getLogger
from uuid import uuid4
import re

from google.cloud import dns

from .base import BaseProvider
from ..record import Record


class GoogleCloudProvider(BaseProvider):
    """
    Google Cloud DNS provider

    google_cloud:
        class: octodns.provider.googlecloud.GoogleCloudProvider
        # Credentials file for a service_account or other account can be
        # specified with the GOOGLE_APPLICATION_CREDENTIALS environment
        # variable. (https://console.cloud.google.com/apis/credentials)
        #
        # The project to work on (not required)
        # project: foobar
        #
        # The File with the google credentials (not required). If used, the
        # "project" parameter needs to be set, else it will fall back to the
        #  "default credentials"
        # credentials_file: ~/google_cloud_credentials_file.json
        #
    """

    SUPPORTS = set(('A', 'AAAA', 'CAA', 'CNAME', 'MX', 'NAPTR',
                    'NS', 'PTR', 'SPF', 'SRV', 'TXT'))
    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS_ROOT_NS = False

    CHANGE_LOOP_WAIT = 5

    def __init__(self, id, project=None, credentials_file=None,
                 *args, **kwargs):

        if credentials_file:
            self.gcloud_client = dns.Client.from_service_account_json(
                credentials_file, project=project)
        else:
            self.gcloud_client = dns.Client(project=project)

        # Logger
        self.log = getLogger('GoogleCloudProvider[{}]'.format(id))
        self.id = id

        self._gcloud_zones = {}

        super(GoogleCloudProvider, self).__init__(id, *args, **kwargs)

    def _apply(self, plan):
        """Required function of manager.py to actually apply a record change.

            :param plan: Contains the zones and changes to be made
            :type  plan: octodns.provider.base.Plan

            :type return: void
        """
        desired = plan.desired
        changes = plan.changes

        self.log.debug('_apply: zone=%s, len(changes)=%d', desired.name,
                       len(changes))

        # Get gcloud zone, or create one if none existed before.
        if desired.name not in self.gcloud_zones:
            gcloud_zone = self._create_gcloud_zone(desired.name)
        else:
            gcloud_zone = self.gcloud_zones.get(desired.name)

        gcloud_changes = gcloud_zone.changes()

        for change in changes:
            class_name = change.__class__.__name__
            _rrset_func = getattr(
                self, '_rrset_for_{}'.format(change.record._type))

            if class_name == 'Create':
                gcloud_changes.add_record_set(
                    _rrset_func(gcloud_zone, change.record))
            elif class_name == 'Delete':
                gcloud_changes.delete_record_set(
                    _rrset_func(gcloud_zone, change.record))
            elif class_name == 'Update':
                gcloud_changes.delete_record_set(
                    _rrset_func(gcloud_zone, change.existing))
                gcloud_changes.add_record_set(
                    _rrset_func(gcloud_zone, change.new))
            else:
                raise RuntimeError('Change type "{}" for change "{!s}" '
                                   'is none of "Create", "Delete" or "Update'
                                   .format(class_name, change))

        gcloud_changes.create()

        for i in range(120):
            gcloud_changes.reload()
            # https://cloud.google.com/dns/api/v1/changes#resource
            # status can be one of either "pending" or "done"
            if gcloud_changes.status != 'pending':
                break
            self.log.debug("Waiting for changes to complete")
            time.sleep(self.CHANGE_LOOP_WAIT)

        if gcloud_changes.status != 'done':
            raise RuntimeError("Timeout reached after {} seconds".format(
                i * self.CHANGE_LOOP_WAIT))

    def _create_gcloud_zone(self, dns_name):
        """Creates a google cloud ManagedZone with dns_name, and zone named
            derived from it. calls .create() method and returns it.

            :param dns_name: fqdn of zone to create
            :type  dns_name: str

            :type return: new google.cloud.dns.ManagedZone
        """
        # Zone name must begin with a letter, end with a letter or digit,
        # and only contain lowercase letters, digits or dashes,
        # and be 63 characters or less
        zone_name = 'zone-{}-{}'.format(
            dns_name.replace('.', '-'), uuid4().hex)[:63]

        gcloud_zone = self.gcloud_client.zone(
            name=zone_name,
            dns_name=dns_name
        )
        gcloud_zone.create(client=self.gcloud_client)

        # add this new zone to the list of zones.
        self._gcloud_zones[gcloud_zone.dns_name] = gcloud_zone

        self.log.info("Created zone {}. Fqdn {}.".format(zone_name, dns_name))

        return gcloud_zone

    def _get_gcloud_records(self, gcloud_zone, page_token=None):
        """ Generator function which yields ResourceRecordSet for the managed
            gcloud zone, until there are no more records to pull.

            :param gcloud_zone: zone to pull records from
            :type gcloud_zone: google.cloud.dns.ManagedZone
            :param page_token: page token for the page to get

            :return: a resource record set
            :type return: google.cloud.dns.ResourceRecordSet
        """
        gcloud_iterator = gcloud_zone.list_resource_record_sets(
            page_token=page_token)
        for gcloud_record in gcloud_iterator:
            yield gcloud_record
        # This is to get results which may be on a "paged" page.
        # (if more than max_results) entries.
        if gcloud_iterator.next_page_token:
            for gcloud_record in self._get_gcloud_records(
                    gcloud_zone, gcloud_iterator.next_page_token):
                # yield from is in python 3 only.
                yield gcloud_record

    def _get_cloud_zones(self, page_token=None):
        """Load all ManagedZones into the self._gcloud_zones dict which is
        mapped with the dns_name as key.

        :return: void
        """

        gcloud_zones = self.gcloud_client.list_zones(page_token=page_token)
        for gcloud_zone in gcloud_zones:
            self._gcloud_zones[gcloud_zone.dns_name] = gcloud_zone

        if gcloud_zones.next_page_token:
            self._get_cloud_zones(gcloud_zones.next_page_token)

    @property
    def gcloud_zones(self):
        if not self._gcloud_zones:
            self._get_cloud_zones()
        return self._gcloud_zones

    def populate(self, zone, target=False, lenient=False):
        """Required function of manager.py to collect records from zone.

            :param zone: A dns zone
            :type  zone: octodns.zone.Zone
            :param target: Unused.
            :type  target: bool
            :param lenient: Unused. Check octodns.manager for usage.
            :type  lenient: bool

            :type return: void
        """

        self.log.debug('populate: name=%s, target=%s, lenient=%s', zone.name,
                       target, lenient)

        exists = False
        before = len(zone.records)

        gcloud_zone = self.gcloud_zones.get(zone.name)

        if gcloud_zone:
            exists = True
            for gcloud_record in self._get_gcloud_records(gcloud_zone):
                if gcloud_record.record_type.upper() not in self.SUPPORTS:
                    continue

                record_name = gcloud_record.name
                if record_name.endswith(zone.name):
                    # google cloud always return fqdn. Make relative record
                    # here. "root" records will then get the '' record_name,
                    # which is also the way octodns likes it.
                    record_name = record_name[:-(len(zone.name) + 1)]
                typ = gcloud_record.record_type.upper()
                data = getattr(self, '_data_for_{}'.format(typ))
                data = data(gcloud_record)
                data['type'] = typ
                data['ttl'] = gcloud_record.ttl
                self.log.debug('populate: adding record {} records: {!s}'
                               .format(record_name, data))
                record = Record.new(zone, record_name, data, source=self)
                zone.add_record(record, lenient=lenient)

        self.log.info('populate: found %s records, exists=%s',
                      len(zone.records) - before, exists)
        return exists

    def _data_for_A(self, gcloud_record):
        return {
            'values': gcloud_record.rrdatas
        }

    _data_for_AAAA = _data_for_A

    def _data_for_CAA(self, gcloud_record):
        return {
            'values': [{
                'flags': v[0],
                'tag': v[1],
                'value': v[2]}
                for v in [shlex.split(g) for g in gcloud_record.rrdatas]]}

    def _data_for_CNAME(self, gcloud_record):
        return {
            'value': gcloud_record.rrdatas[0]
        }

    def _data_for_MX(self, gcloud_record):
        return {'values': [{
            "preference": v[0],
            "exchange": v[1]}
            for v in [shlex.split(g) for g in gcloud_record.rrdatas]]}

    def _data_for_NAPTR(self, gcloud_record):
        return {'values': [{
            'order': v[0],
            'preference': v[1],
            'flags': v[2],
            'service': v[3],
            'regexp': v[4],
            'replacement': v[5]}
            for v in [shlex.split(g) for g in gcloud_record.rrdatas]]}

    _data_for_NS = _data_for_A

    _data_for_PTR = _data_for_CNAME

    _fix_semicolons = re.compile(r'(?<!\\);')

    def _data_for_SPF(self, gcloud_record):
        if len(gcloud_record.rrdatas) > 1:
            return {
                'values': [self._fix_semicolons.sub('\\;', rr)
                           for rr in gcloud_record.rrdatas]}
        return {
            'value': self._fix_semicolons.sub('\\;', gcloud_record.rrdatas[0])}

    def _data_for_SRV(self, gcloud_record):
        return {'values': [{
            'priority': v[0],
            'weight': v[1],
            'port': v[2],
            'target': v[3]}
            for v in [shlex.split(g) for g in gcloud_record.rrdatas]]}

    _data_for_TXT = _data_for_SPF

    def _rrset_for_A(self, gcloud_zone, record):
        return gcloud_zone.resource_record_set(
            record.fqdn, record._type, record.ttl, record.values)

    _rrset_for_AAAA = _rrset_for_A

    def _rrset_for_CAA(self, gcloud_zone, record):
        return gcloud_zone.resource_record_set(
            record.fqdn, record._type, record.ttl, [
                '{} {} {}'.format(v.flags, v.tag, v.value)
                for v in record.values])

    def _rrset_for_CNAME(self, gcloud_zone, record):
        return gcloud_zone.resource_record_set(
            record.fqdn, record._type, record.ttl, [record.value])

    def _rrset_for_MX(self, gcloud_zone, record):
        return gcloud_zone.resource_record_set(
            record.fqdn, record._type, record.ttl, [
                '{} {}'.format(v.preference, v.exchange)
                for v in record.values])

    def _rrset_for_NAPTR(self, gcloud_zone, record):
        return gcloud_zone.resource_record_set(
            record.fqdn, record._type, record.ttl, [
                '{} {} "{}" "{}" "{}" {}'.format(
                    v.order, v.preference, v.flags, v.service,
                    v.regexp, v.replacement) for v in record.values])

    _rrset_for_NS = _rrset_for_A

    _rrset_for_PTR = _rrset_for_CNAME

    def _rrset_for_SPF(self, gcloud_zone, record):
        return gcloud_zone.resource_record_set(
            record.fqdn, record._type, record.ttl, record.chunked_values)

    def _rrset_for_SRV(self, gcloud_zone, record):
        return gcloud_zone.resource_record_set(
            record.fqdn, record._type, record.ttl, [
                '{} {} {} {}'
                .format(v.priority, v.weight, v.port, v.target)
                for v in record.values])

    _rrset_for_TXT = _rrset_for_SPF
