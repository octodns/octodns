#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from collections import defaultdict
from logging import getLogger
import re

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
            raise Exception(f'Invalid zone name {name}, missing ending dot')
        # Force everything to lowercase just to be safe
        self.name = str(name).lower() if name else name
        self.sub_zones = sub_zones
        # We're grouping by node, it allows us to efficiently search for
        # duplicates and detect when CNAMEs co-exist with other records
        self._records = defaultdict(set)
        self._root_ns = None
        # optional leading . to match empty hostname
        # optional trailing . b/c some sources don't have it on their fqdn
        self._name_re = re.compile(fr'\.?{name}?$')

        # Copy-on-write semantics support, when `not None` this property will
        # point to a location with records for this `Zone`. Once `hydrated`
        # this property will be set to None
        self._origin = None

        self.log.debug('__init__: zone=%s, sub_zones=%s', self, sub_zones)

    @property
    def records(self):
        if self._origin:
            return self._origin.records
        return set([r for _, node in self._records.items() for r in node])

    @property
    def root_ns(self):
        if self._origin:
            return self._origin.root_ns
        return self._root_ns

    def hostname_from_fqdn(self, fqdn):
        return self._name_re.sub('', fqdn)

    def add_record(self, record, replace=False, lenient=False):
        if self._origin:
            self.hydrate()

        name = record.name
        last = name.split('.')[-1]

        if not lenient and last in self.sub_zones:
            if name != last:
                # it's a record for something under a sub-zone
                raise SubzoneRecordException(f'Record {record.fqdn} is under '
                                             'a managed subzone')
            elif record._type != 'NS':
                # It's a non NS record for exactly a sub-zone
                raise SubzoneRecordException(f'Record {record.fqdn} a '
                                             'managed sub-zone and not of '
                                             'type NS')

        if replace:
            # will remove it if it exists
            self._records[name].discard(record)

        node = self._records[name]
        if record in node:
            # We already have a record at this node of this type
            raise DuplicateRecordException(f'Duplicate record {record.fqdn}, '
                                           f'type {record._type}')
        elif not lenient and ((record._type == 'CNAME' and len(node) > 0) or
                              ('CNAME' in [r._type for r in node])):
            # We're adding a CNAME to existing records or adding to an existing
            # CNAME
            raise InvalidNodeException('Invalid state, CNAME at '
                                       f'{record.fqdn} cannot coexist with '
                                       'other records')

        if record._type == 'NS' and record.name == '':
            self._root_ns = record

        node.add(record)

    def remove_record(self, record):
        if self._origin:
            self.hydrate()

        if record._type == 'NS' and record.name == '':
            self._root_ns = None

        self._records[record.name].discard(record)

    # TODO: delete this
    _remove_record = remove_record

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

    def hydrate(self):
        '''
        Take a shallow copy Zone and make it a deeper copy holding its own
        reference to records. These records will still be the originals and
        they should not be modified. Changes should be made by calling
        `add_record`, often with `replace=True`, and/or `remove_record`.

        Note: This method does not need to be called under normal circumstances
        as `add_record` and `remove_record` will automatically call it when
        appropriate.
        '''
        origin = self._origin
        if origin is None:
            return False
        # Need to clear this before the copy to prevent recursion
        self._origin = None
        for record in origin.records:
            # Use lenient as we're copying origin and should take its records
            # regardless
            self.add_record(record, lenient=True)
        return True

    def copy(self):
        '''
        Copy-on-write semantics support. This method will create a shallow
        clone of the zone which will be hydrated the first time `add_record` or
        `remove_record` is called.

        This allows low-cost copies of things to be made in situations where
        changes are unlikely and only incurs the "expense" of actually
        copying the records when required. The actual record copy will not be
        "deep" meaning that records should not be modified directly.
        '''
        copy = Zone(self.name, self.sub_zones)
        copy._origin = self
        return copy

    def __repr__(self):
        return f'Zone<{self.name}>'
