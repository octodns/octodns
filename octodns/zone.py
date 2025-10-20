#
#
#

import re
from collections import defaultdict
from logging import getLogger

from .deprecation import deprecated
from .idna import idna_decode, idna_encode
from .record import Create, Delete


class SubzoneRecordException(Exception):
    '''
    Exception raised when a record belongs in a sub-zone but is added to the parent.

    This exception is raised when attempting to add a record to a zone that
    should actually be managed in a configured sub-zone. Only NS and DS records
    are allowed at the sub-zone boundary.

    :param record: The record that caused the exception.
    :type record: octodns.record.base.Record
    '''

    def __init__(self, msg, record):
        self.record = record

        if record.context:
            msg += f', {record.context}'

        super().__init__(msg)


class DuplicateRecordException(Exception):
    '''
    Exception raised when attempting to add a duplicate record to a zone.

    A duplicate is defined as a record with the same name and type as an
    existing record in the zone. The exception includes references to both
    the existing and new records for debugging.

    :param existing: The existing record in the zone.
    :type existing: octodns.record.base.Record
    :param new: The new record being added.
    :type new: octodns.record.base.Record
    '''

    def __init__(self, msg, existing, new):
        self.existing = existing
        self.new = new

        if existing.context:
            if new.context:
                # both have context
                msg += f'\n  existing: {existing.context}\n  new:      {new.context}'
            else:
                # only existing has context
                msg += (
                    f'\n  existing: {existing.context}\n  new:      [UNKNOWN]'
                )
        elif new.context:
            # only new has context
            msg += f'\n  existing: [UNKNOWN]\n  new:      {new.context}'
        # else no one has context

        super().__init__(msg)


class InvalidNodeException(Exception):
    '''
    Exception raised when CNAME records coexist with other records at a node.

    Per DNS standards, CNAME records cannot coexist with other record types
    at the same node. This exception is raised when such an invalid
    configuration is detected.

    :param record: The record that caused the exception.
    :type record: octodns.record.base.Record
    '''

    def __init__(self, msg, record):
        self.record = record

        if record.context:
            msg += f', {record.context}'

        super().__init__(msg)


class InvalidNameError(Exception):
    '''
    Exception raised when a zone name is invalid.

    Zone names must:
    - End with a dot (.)
    - Not contain double dots (..)
    - Not contain whitespace
    '''

    pass


class Zone(object):
    '''
    Container for DNS records belonging to a single DNS zone.

    A Zone represents a DNS zone and manages all the records within it. It
    provides methods for adding, removing, and querying records, as well as
    computing changes between zones and applying those changes.

    Zones support copy-on-write semantics via the :meth:`copy` method, which
    creates shallow copies that are hydrated on first modification. This allows
    for efficient processing of zones through multiple stages without
    unnecessary copying.

    Key features:

    - **Record management**: Add, remove, and query DNS records
    - **Validation**: Enforce DNS standards (CNAME restrictions, sub-zone rules)
    - **IDNA support**: Handle internationalized domain names
    - **Sub-zone awareness**: Respect configured sub-zone boundaries
    - **Change tracking**: Compute differences between desired and existing state
    - **Copy-on-write**: Efficient shallow copying with lazy hydration

    Example usage::

      from octodns.zone import Zone
      from octodns.record import Record

      zone = Zone('example.com.', [])
      record = Record.new(zone, 'www', {'type': 'A', 'ttl': 300, 'value': '1.2.3.4'})
      zone.add_record(record)

      # Create a shallow copy
      copy = zone.copy()
      # Modifications to copy don't affect the original until hydrated

    See Also:
        - :doc:`/zone_lifecycle` for details on zone processing workflow
        - :class:`octodns.record.base.Record`
        - :class:`octodns.provider.base.BaseProvider`
    '''

    log = getLogger('Zone')

    def __init__(
        self,
        name,
        sub_zones,
        update_pcent_threshold=None,
        delete_pcent_threshold=None,
    ):
        '''
        Initialize a DNS zone.

        :param name: The zone name (must end with a dot). Internationalized
                     domain names (IDN) are automatically encoded to IDNA format.
        :type name: str
        :param sub_zones: List of sub-zone names managed separately. Records
                          belonging to sub-zones will be rejected (except NS/DS
                          at the boundary).
        :type sub_zones: list[str]
        :param update_pcent_threshold: Override for maximum update percentage
                                       threshold. If None, uses provider default.
        :type update_pcent_threshold: float or None
        :param delete_pcent_threshold: Override for maximum delete percentage
                                       threshold. If None, uses provider default.
        :type delete_pcent_threshold: float or None

        :raises InvalidNameError: If the zone name is invalid (missing trailing
                                  dot, contains double dots, or has whitespace).

        .. important::
           - Zone names must end with a dot (.)
           - Zone names are automatically encoded to IDNA format internally
           - Sub-zones prevent records from being added to the parent zone
        '''
        if not name[-1] == '.':
            raise InvalidNameError(
                f'Invalid zone name {name}, missing ending dot'
            )
        elif '..' in name:
            raise InvalidNameError(
                f'Invalid zone name {name}, double dot not allowed'
            )
        elif ' ' in name or '\t' in name:
            raise InvalidNameError(
                f'Invalid zone name {name}, whitespace not allowed'
            )

        # internally everything is idna
        self.name = idna_encode(str(name)) if name else name
        # we'll keep a decoded version around for logs and errors
        self.decoded_name = idna_decode(self.name)
        self.sub_zones = sub_zones
        # We're grouping by node, it allows us to efficiently search for
        # duplicates and detect when CNAMEs co-exist with other records. Also
        # node that we always store things with Record.name which will be idna
        # encoded thus we don't have to deal with idna/utf8 collisions
        self._records = defaultdict(set)
        self._root_ns = None
        # optional leading . to match empty hostname
        # optional trailing . b/c some sources don't have it on their fqdn
        self._utf8_name_re = re.compile(fr'\.?{idna_decode(name)}?$')
        self._idna_name_re = re.compile(fr'\.?{self.name}?$')

        self.update_pcent_threshold = update_pcent_threshold
        self.delete_pcent_threshold = delete_pcent_threshold

        # Copy-on-write semantics support, when `not None` this property will
        # point to a location with records for this `Zone`. Once `hydrated`
        # this property will be set to None
        self._origin = None

        self.log.debug('__init__: zone=%s, sub_zones=%s', self, sub_zones)

    @property
    def records(self):
        '''
        Get all records in this zone.

        Returns a set of all DNS records in the zone. If this is a shallow copy
        (not yet hydrated), returns records from the origin zone.

        :return: Set of all records in the zone.
        :rtype: set[octodns.record.base.Record]
        '''
        if self._origin:
            return self._origin.records
        return set([r for _, node in self._records.items() for r in node])

    @property
    def root_ns(self):
        '''
        Get the root NS record for this zone.

        The root NS record is the NS record at the zone apex (empty hostname).
        Returns None if no root NS record exists.

        :return: The root NS record, or None if not present.
        :rtype: octodns.record.ns.NsRecord or None
        '''
        if self._origin:
            return self._origin.root_ns
        return self._root_ns

    def hostname_from_fqdn(self, fqdn):
        '''
        Extract the hostname portion from a fully qualified domain name.

        Strips the zone name from the FQDN to get just the hostname portion.
        Handles both IDNA-encoded and UTF-8 domain names correctly.

        :param fqdn: Fully qualified domain name.
        :type fqdn: str

        :return: The hostname portion (without the zone name).
        :rtype: str

        Example::

          zone = Zone('example.com.', [])
          zone.hostname_from_fqdn('www.example.com.')  # Returns 'www'
          zone.hostname_from_fqdn('example.com.')      # Returns ''
        '''
        try:
            fqdn.encode('ascii')
            # it's non-idna or idna encoded
            return self._idna_name_re.sub('', idna_encode(fqdn))
        except UnicodeEncodeError:
            # it has utf8 chars
            return self._utf8_name_re.sub('', fqdn)

    def owns(self, _type, fqdn):
        '''
        Determine if this zone owns a given FQDN for a specific record type.

        Checks whether a record with the given FQDN and type should be managed
        by this zone, taking into account sub-zone boundaries. Records under
        sub-zones are not owned by the parent (except NS records at the exact
        sub-zone boundary).

        :param _type: The DNS record type (e.g., 'A', 'CNAME', 'NS').
        :type _type: str
        :param fqdn: Fully qualified domain name to check.
        :type fqdn: str

        :return: True if this zone owns the FQDN for this type, False otherwise.
        :rtype: bool

        .. important::
           - NS records at sub-zone boundaries are owned by the parent zone
           - All other records under sub-zones are not owned by the parent
           - FQDNs are automatically normalized (trailing dot added if missing)
        '''
        if fqdn[-1] != '.':
            fqdn = f'{fqdn}.'

        # if we exactly match the zone name we own it
        if fqdn == self.name:
            return True

        # if we don't end with the zone's name on a boundary we aren't owned
        if not fqdn.endswith(f'.{self.name}'):
            return False

        hostname = self.hostname_from_fqdn(fqdn)
        if hostname in self.sub_zones:
            # if our hostname matches a sub-zone exactly we have to be a NS
            # record
            return _type == 'NS'

        for sub_zone in self.sub_zones:
            if hostname.endswith(f'.{sub_zone}'):
                # this belongs under a sub-zone
                return False

        # otherwise we own it
        return True

    def add_record(self, record, replace=False, lenient=False):
        '''
        Add a DNS record to this zone.

        Adds the provided record to the zone with validation. If this is a
        shallow copy (has an origin), it will be hydrated before adding.

        :param record: The DNS record to add to the zone.
        :type record: octodns.record.base.Record
        :param replace: If True, replace any existing record with the same name
                        and type. If False, raise an exception if a duplicate
                        exists.
        :type replace: bool
        :param lenient: If True, skip some validation checks (sub-zone checks,
                        CNAME coexistence checks). Useful when loading existing
                        data that may not be standards-compliant.
        :type lenient: bool

        :raises SubzoneRecordException: If the record belongs in a configured
                                        sub-zone (unless it's an NS/DS record
                                        at the boundary).
        :raises DuplicateRecordException: If a record with the same name and type
                                          already exists and ``replace=False``.
        :raises InvalidNodeException: If adding the record would create an
                                      invalid CNAME coexistence situation.

        .. important::
           - Automatically hydrates shallow copies on first modification
           - NS/DS records are allowed at sub-zone boundaries
           - CNAME records cannot coexist with other records at the same node
           - Use ``replace=True`` to update existing records
           - Use ``lenient=True`` when loading potentially non-compliant data
        '''
        if self._origin:
            self.hydrate()

        name = record.name

        if not lenient:
            if name in self.sub_zones:
                # It's an exact match for a sub-zone
                if not (record._type == 'NS' or record._type == 'DS'):
                    # and not a NS or DS record, this should be in the sub
                    raise SubzoneRecordException(
                        f'Record {record.fqdn} is a managed sub-zone and not of type NS or DS',
                        record,
                    )
            else:
                # It's not an exact match so there has to be a `.` before the
                # sub-zone for it to belong in there
                for sub_zone in self.sub_zones:
                    if name.endswith(f'.{sub_zone}'):
                        # this should be in a sub
                        raise SubzoneRecordException(
                            f'Record {record.fqdn} is under a managed subzone',
                            record,
                        )

        if replace:
            # will remove it if it exists
            self._records[name].discard(record)

        node = self._records[name]
        new_lenient = record.lenient
        existing_lenient = all(r.lenient for r in node)
        if record in node:
            # We already have a record at this node of this type
            existing = [c for c in node if c == record][0]
            raise DuplicateRecordException(
                f'Duplicate record {record.fqdn}, type {record._type}',
                existing,
                record,
            )
        elif (
            # add was not called with lenience
            not lenient
            # existing and new records aren't lenient
            and not (existing_lenient and new_lenient)
            # and there'll be a CNAME co-existing with other records
            and (
                (record._type == 'CNAME' and len(node) > 0)
                or ('CNAME' in [r._type for r in node])
            )
        ):
            # We're adding a CNAME to existing records or adding to an existing
            # CNAME
            raise InvalidNodeException(
                f'Invalid state, CNAME at {record.fqdn} cannot coexist with other records',
                record,
            )

        if record._type == 'NS' and record.name == '':
            self._root_ns = record

        node.add(record)

    def remove_record(self, record):
        '''
        Remove a DNS record from this zone.

        Removes the provided record from the zone. If this is a shallow copy
        (has an origin), it will be hydrated before removing.

        :param record: The DNS record to remove from the zone.
        :type record: octodns.record.base.Record

        .. important::
           - Automatically hydrates shallow copies on first modification
           - Clearing the root NS record (empty name) also clears the cached
             ``root_ns`` property
           - Silently succeeds if the record doesn't exist in the zone
        '''
        if self._origin:
            self.hydrate()

        if record._type == 'NS' and record.name == '':
            self._root_ns = None

        self._records[record.name].discard(record)

    # TODO: delete this at v2.0.0rc0
    def _remove_record(self, record):
        deprecated(
            '_remove_record has been deprecated, used remove_record instead.  Will be removed in 2.0',
            stacklevel=3,
        )
        return self.remove_record(record)

    def changes(self, desired, target):
        '''
        Compute the changes needed to transform this zone into the desired state.

        Compares this zone (existing state) with the desired zone and returns
        a list of changes (Creates, Updates, Deletes) required to make this
        zone match the desired state. Respects record-level include/exclude
        filtering and provider support.

        :param desired: The desired zone state to compare against.
        :type desired: Zone
        :param target: The target provider that will apply these changes. Used
                       to check record support and apply include/exclude rules.
        :type target: octodns.provider.base.BaseProvider

        :return: List of changes needed to transform this zone to the desired state.
        :rtype: list[octodns.record.change.Change]

        .. important::
           - Skips records marked as ``ignored``
           - Respects record-level ``included`` and ``excluded`` lists
           - Only includes changes for record types the target supports
           - Returns Creates, Updates (via record.changes), and Deletes
        '''
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
            elif len(record.included) > 0 and target.id not in record.included:
                self.log.debug(
                    'changes:  skipping record=%s %s - %s not included ',
                    record.fqdn,
                    record._type,
                    target.id,
                )
                continue
            elif target.id in record.excluded:
                self.log.debug(
                    'changes:  skipping record=%s %s - %s excluded ',
                    record.fqdn,
                    record._type,
                    target.id,
                )
                continue
            try:
                desired_record = desired_records[record]
                if desired_record.ignored:
                    continue
                elif (
                    len(desired_record.included) > 0
                    and target.id not in desired_record.included
                ):
                    self.log.debug(
                        'changes:  skipping record=%s %s - %s not included',
                        record.fqdn,
                        record._type,
                        target.id,
                    )
                    continue
                elif target.id in desired_record.excluded:
                    continue
            except KeyError:
                if not target.supports(record):
                    self.log.debug(
                        'changes:  skipping record=%s %s - %s does '
                        'not support it',
                        record.fqdn,
                        record._type,
                        target.id,
                    )
                    continue
                # record has been removed
                self.log.debug(
                    'changes: zone=%s, removed record=%s', self, record
                )
                changes.append(Delete(record))
            else:
                change = record.changes(desired_record, target)
                if change:
                    self.log.debug(
                        'changes: zone=%s, modified\n'
                        '    existing=%s,\n     desired=%s',
                        self,
                        record,
                        desired_record,
                    )
                    changes.append(change)
                else:
                    self.log.debug(
                        'changes: zone=%s, n.c. record=%s', self, record
                    )

        # Find additions, things that are in desired, but missing in ourselves.
        # This uses set math and our special __hash__ and __cmp__ functions as
        # well
        for record in desired.records - self.records:
            if record.ignored:
                continue
            elif len(record.included) > 0 and target.id not in record.included:
                self.log.debug(
                    'changes:  skipping record=%s %s - %s not included ',
                    record.fqdn,
                    record._type,
                    target.id,
                )
                continue
            elif target.id in record.excluded:
                self.log.debug(
                    'changes:  skipping record=%s %s - %s excluded ',
                    record.fqdn,
                    record._type,
                    target.id,
                )
                continue

            if not target.supports(record):
                self.log.debug(
                    'changes:  skipping record=%s %s - %s does not '
                    'support it',
                    record.fqdn,
                    record._type,
                    target.id,
                )
                continue
            self.log.debug('changes: zone=%s, create record=%s', self, record)
            changes.append(Create(record))

        return changes

    def apply(self, changes):
        '''
        Apply a list of changes to this zone.

        Applies the provided changes by adding new/updated records and removing
        deleted records. Uses ``replace=True`` and ``lenient=True`` to handle
        updates and non-standard records gracefully.

        :param changes: List of changes to apply to the zone.
        :type changes: list[octodns.record.change.Change]

        .. important::
           - Delete changes remove the existing record
           - Create and Update changes add the new record with ``replace=True``
           - All adds use ``lenient=True`` to skip validation
           - Changes are applied in the order provided
        '''
        for change in changes:
            if isinstance(change, Delete):
                self.remove_record(change.existing)
            else:
                self.add_record(change.new, replace=True, lenient=True)

    def hydrate(self):
        '''
        Convert a shallow copy into a hydrated copy with its own record references.

        Hydration copies all records from the origin zone into this zone,
        making it independent. The records themselves are still the original
        objects and should not be modified directly. Use :meth:`add_record`
        with ``replace=True`` or :meth:`remove_record` to make changes.

        :return: True if hydration occurred, False if already hydrated.
        :rtype: bool

        .. note::
           This method is automatically called by :meth:`add_record` and
           :meth:`remove_record` when needed, so manual calls are rarely necessary.

        .. important::
           - Only hydrates if this is a shallow copy (has an ``_origin``)
           - Clears the ``_origin`` reference after hydration
           - Uses ``lenient=True`` when adding records from origin
           - Records are still shared with the origin (not deep copied)
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
        Create a shallow copy of this zone using copy-on-write semantics.

        Creates a new zone that shares records with this zone until the copy
        is modified. When :meth:`add_record` or :meth:`remove_record` is called
        on the copy, it will be automatically hydrated with its own record
        references.

        :return: A shallow copy of this zone.
        :rtype: Zone

        .. important::
           - The copy shares records with the original until hydrated
           - Hydration happens automatically on first modification
           - Records in the hydrated copy are still the same objects (not deep copied)
           - Modifying records directly affects both zones; use ``record.copy()``
             and ``add_record(..., replace=True)`` instead

        Example::

          original = Zone('example.com.', [])
          # ... add records to original ...

          copy = original.copy()  # Shallow copy, shares records
          # No copying has occurred yet

          copy.add_record(new_record)  # Triggers hydration, copies record refs
          # Now copy has its own record references
        '''
        copy = Zone(
            self.name,
            self.sub_zones,
            self.update_pcent_threshold,
            self.delete_pcent_threshold,
        )
        copy._origin = self
        return copy

    def __repr__(self):
        '''
        Return a string representation of this zone.

        :return: String in the format ``Zone<zone_name>`` using the decoded name.
        :rtype: str
        '''
        return f'Zone<{self.decoded_name}>'
