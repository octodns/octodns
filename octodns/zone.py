#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from collections import defaultdict
from logging import getLogger
import re

from six import text_type

from .record import Create, Delete


class SubzoneRecordException(Exception):
    pass


class DuplicateRecordException(Exception):
    pass


class InvalidNodeException(Exception):
    pass


class Zone(object):
    log = getLogger('Zone')

    def __init__(self, name, sub_zones):
        if not name[-1] == '.':
            raise Exception('Invalid zone name {}, missing ending dot'
                            .format(name))
        # Force everything to lowercase just to be safe
        self.name = text_type(name).lower() if name else name
        self.sub_zones = sub_zones
        # We're grouping by node, it allows us to efficiently search for
        # duplicates and detect when CNAMEs co-exist with other records
        self._records = defaultdict(set)
        # optional leading . to match empty hostname
        # optional trailing . b/c some sources don't have it on their fqdn
        self._name_re = re.compile(r'\.?{}?$'.format(name))

        self.log.debug('__init__: zone=%s, sub_zones=%s', self, sub_zones)

    @property
    def records(self):
        return set([r for _, node in self._records.items() for r in node])

    def hostname_from_fqdn(self, fqdn):
        return self._name_re.sub('', fqdn)

    def add_record(self, record, replace=False, lenient=False):
        name = record.name
        last = name.split('.')[-1]

        if not lenient and last in self.sub_zones:
            if name != last:
                # it's a record for something under a sub-zone
                raise SubzoneRecordException('Record {} is under a '
                                             'managed subzone'
                                             .format(record.fqdn))
            elif record._type != 'NS':
                # It's a non NS record for exactly a sub-zone
                raise SubzoneRecordException('Record {} a managed sub-zone '
                                             'and not of type NS'
                                             .format(record.fqdn))

        if replace:
            # will remove it if it exists
            self._records[name].discard(record)

        node = self._records[name]
        if record in node:
            # We already have a record at this node of this type
            raise DuplicateRecordException('Duplicate record {}, type {}'
                                           .format(record.fqdn,
                                                   record._type))
        elif not lenient and ((record._type == 'CNAME' and len(node) > 0) or
                              ('CNAME' in [r._type for r in node])):
            # We're adding a CNAME to existing records or adding to an existing
            # CNAME
            raise InvalidNodeException('Invalid state, CNAME at {} cannot '
                                       'coexist with other records'
                                       .format(record.fqdn))

        node.add(record)

    def _remove_record(self, record):
        'Only for use in tests'
        self._records[record.name].discard(record)

    def changes(self, desired, target):
        self.log.debug('changes: zone=%s, target=%s', self, target)

        # Build up a hash of the desired records, thanks to our special
        # __hash__ and __cmp__ on Record we'll be able to look up records that
        # match name and _type with it
        desired_records = {r: r for r in desired.records}

        changes = []

        # Find diffs & removes
        for record in self.records:
            if record.ignored:
                continue
            elif len(record.included) > 0 and \
                    target.id not in record.included:
                self.log.debug('changes:  skipping record=%s %s - %s not'
                               ' included ', record.fqdn, record._type,
                               target.id)
                continue
            elif target.id in record.excluded:
                self.log.debug('changes:  skipping record=%s %s - %s '
                               'excluded ', record.fqdn, record._type,
                               target.id)
                continue
            try:
                desired_record = desired_records[record]
                if desired_record.ignored:
                    continue
                elif len(desired_record.included) > 0 and \
                        target.id not in desired_record.included:
                    self.log.debug('changes:  skipping record=%s %s - %s'
                                   'not included ', record.fqdn, record._type,
                                   target.id)
                    continue
                elif target.id in desired_record.excluded:
                    continue
            except KeyError:
                if not target.supports(record):
                    self.log.debug('changes:  skipping record=%s %s - %s does '
                                   'not support it', record.fqdn, record._type,
                                   target.id)
                    continue
                # record has been removed
                self.log.debug('changes: zone=%s, removed record=%s', self,
                               record)
                changes.append(Delete(record))
            else:
                change = record.changes(desired_record, target)
                if change:
                    self.log.debug('changes: zone=%s, modified\n'
                                   '    existing=%s,\n     desired=%s', self,
                                   record, desired_record)
                    changes.append(change)
                else:
                    self.log.debug('changes: zone=%s, n.c. record=%s', self,
                                   record)

        # Find additions, things that are in desired, but missing in ourselves.
        # This uses set math and our special __hash__ and __cmp__ functions as
        # well
        for record in desired.records - self.records:
            if record.ignored:
                continue
            elif len(record.included) > 0 and \
                    target.id not in record.included:
                self.log.debug('changes:  skipping record=%s %s - %s not'
                               ' included ', record.fqdn, record._type,
                               target.id)
                continue
            elif target.id in record.excluded:
                self.log.debug('changes:  skipping record=%s %s - %s '
                               'excluded ', record.fqdn, record._type,
                               target.id)
                continue

            if not target.supports(record):
                self.log.debug('changes:  skipping record=%s %s - %s does not '
                               'support it', record.fqdn, record._type,
                               target.id)
                continue
            self.log.debug('changes: zone=%s, create record=%s', self, record)
            changes.append(Create(record))

        return changes

    def __repr__(self):
        return 'Zone<{}>'.format(self.name)
