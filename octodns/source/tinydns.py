#
#
#

import logging
import textwrap
from collections import defaultdict
from ipaddress import ip_address
from os import listdir
from os.path import join

from ..record import Record
from .base import BaseSource


def _unique(values):
    try:
        # this will work if they're simple strings
        return list(set(values))
    except TypeError:
        pass
    # if they're dictionaries it's a bit more involved since dict's aren't
    # hashable, based on https://stackoverflow.com/a/38521207
    return [dict(s) for s in set(frozenset(v.items()) for v in values)]


class TinyDnsBaseSource(BaseSource):
    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False

    def __init__(self, id, default_ttl=3600):
        super().__init__(id)
        self.default_ttl = default_ttl

    @property
    def SUPPORTS(self):
        # All record types, including those registered by 3rd party modules
        return set(Record.registered_types().keys())

    def _ttl_for(self, lines, index):
        # see if we can find a ttl on any of the lines, first one wins
        for line in lines:
            try:
                return int(line[index])
            except IndexError:
                pass
        # and if we don't use the default
        return self.default_ttl

    def _records_for_at(self, zone, name, lines, arpa=False):
        # @fqdn:ip:x:dist:ttl:timestamp:lo
        # MX (and optional A)

        if arpa:
            # no arpa
            return []

        if not zone.owns('MX', name):
            # if name doesn't live under our zone there's nothing for us to do
            return

        ttl = self._ttl_for(lines, 4)

        values = []
        for line in lines:
            mx = line[2]
            # if there's a . in the mx we hit a special case and use it as-is
            if '.' not in mx:
                # otherwise we treat it as the MX hostnam and construct the rest
                mx = f'{mx}.mx.{zone.name}'
            elif mx[-1] != '.':
                mx = f'{mx}.'

            # default distance is 0
            try:
                dist = line[3] or 0
            except IndexError:
                dist = 0

            # if we have an IP then we need to create an A for the MX
            ip = line[1]
            if ip and zone.owns('A', mx):
                yield 'A', mx, ttl, [ip]

            values.append({'preference': dist, 'exchange': mx})

        yield 'MX', name, ttl, values

    def _records_for_C(self, zone, name, lines, arpa=False):
        # Cfqdn:p:ttl:timestamp:lo
        # CNAME

        if arpa:
            # no arpa
            return []

        if not zone.owns('CNAME', name):
            # if name doesn't live under our zone there's nothing for us to do
            return

        value = lines[0][1]
        if value[-1] != '.':
            value = f'{value}.'

        ttl = self._ttl_for(lines, 2)

        yield 'CNAME', name, ttl, [value]

    def _records_for_caret(self, zone, name, lines, arpa=False):
        # ^fqdn:p:ttl:timestamp:lo
        # PTR, line may be a A/AAAA or straight PTR

        if not arpa:
            # we only operate on arpa
            return []

        names = defaultdict(list)
        for line in lines:
            if line[0].endswith('in-addr.arpa') or line[0].endswith(
                'ip6.arpa.'
            ):
                # it's a straight PTR record, already in in-addr.arpa format,
                # 2nd item is the name it points to
                name = line[0]
                value = line[1]
            else:
                # it's not a PTR we need to build up the PTR data from what
                # we're given
                value = line[0]
                addr = line[1]
                if '.' not in addr:
                    addr = u':'.join(textwrap.wrap(line[1], 4))
                addr = ip_address(addr)
                name = addr.reverse_pointer

            if value[-1] != '.':
                value = f'{value}.'
            names[name].append(value)

        ttl = self._ttl_for(lines, 2)

        for name, values in names.items():
            if zone.owns('PTR', name):
                yield 'PTR', name, ttl, values

    def _records_for_equal(self, zone, name, lines, arpa=False):
        # =fqdn:ip:ttl:timestamp:lo
        # A (arpa False) & PTR (arpa True)
        if arpa:
            yield from self._records_for_caret(zone, name, lines, arpa)
        else:
            yield from self._records_for_plus(zone, name, lines, arpa)

    def _records_for_dot(self, zone, name, lines, arpa=False):
        # .fqdn:ip:x:ttl:timestamp:lo
        # NS (and optional A)

        if arpa:
            # no arpa
            return []

        if not zone.owns('NS', name):
            # if name doesn't live under our zone there's nothing for us to do
            return

        ttl = self._ttl_for(lines, 3)

        values = []
        for line in lines:
            ns = line[2]
            # if there's a . in the ns we hit a special case and use it as-is
            if '.' not in ns:
                # otherwise we treat it as the NS hostnam and construct the rest
                ns = f'{ns}.ns.{zone.name}'
            elif ns[-1] != '.':
                ns = f'{ns}.'

            # if we have an IP then we need to create an A for the MX
            ip = line[1]
            if ip and zone.owns('A', ns):
                yield 'A', ns, ttl, [ip]

            values.append(ns)

        yield 'NS', name, ttl, values

    _records_for_amp = _records_for_dot

    def _records_for_plus(self, zone, name, lines, arpa=False):
        # +fqdn:ip:ttl:timestamp:lo
        # A

        if arpa:
            # no arpa
            return []

        if not zone.owns('A', name):
            # if name doesn't live under our zone there's nothing for us to do
            return

        # collect our ip(s)
        ips = [l[1] for l in lines if l[1] != '0.0.0.0']

        if not ips:
            # we didn't find any value ips so nothing to do
            return []

        ttl = self._ttl_for(lines, 2)

        yield 'A', name, ttl, ips

    def _records_for_quote(self, zone, name, lines, arpa=False):
        # 'fqdn:s:ttl:timestamp:lo
        # TXT

        if arpa:
            # no arpa
            return []

        if not zone.owns('TXT', name):
            # if name doesn't live under our zone there's nothing for us to do
            return

        # collect our ip(s)
        values = [
            l[1].encode('latin1').decode('unicode-escape').replace(";", "\\;")
            for l in lines
        ]

        ttl = self._ttl_for(lines, 2)

        yield 'TXT', name, ttl, values

    def _records_for_three(self, zone, name, lines, arpa=False):
        # 3fqdn:ip:ttl:timestamp:lo
        # AAAA

        if arpa:
            # no arpa
            return []

        if not zone.owns('AAAA', name):
            # if name doesn't live under our zone there's nothing for us to do
            return

        # collect our ip(s)
        ips = []
        for line in lines:
            # TinyDNS files have the ipv6 address written in full, but with the
            # colons removed. This inserts a colon every 4th character to make
            # the address correct.
            ips.append(u':'.join(textwrap.wrap(line[1], 4)))

        ttl = self._ttl_for(lines, 2)

        yield 'AAAA', name, ttl, ips

    def _records_for_S(self, zone, name, lines, arpa=False):
        # Sfqdn:ip:x:port:priority:weight:ttl:timestamp:lo
        # SRV

        if arpa:
            # no arpa
            return []

        if not zone.owns('SRV', name):
            # if name doesn't live under our zone there's nothing for us to do
            return

        ttl = self._ttl_for(lines, 6)

        values = []
        for line in lines:
            target = line[2]
            # if there's a . in the mx we hit a special case and use it as-is
            if '.' not in target:
                # otherwise we treat it as the MX hostnam and construct the rest
                target = f'{target}.srv.{zone.name}'
            elif target[-1] != '.':
                target = f'{target}.'

            # if we have an IP then we need to create an A for the SRV
            # has to be present, but can be empty
            ip = line[1]
            if ip and zone.owns('A', target):
                yield 'A', target, ttl, [ip]

            # required
            port = int(line[3])

            # optional, default 0
            try:
                priority = int(line[4] or 0)
            except IndexError:
                priority = 0

            # optional, default 0
            try:
                weight = int(line[5] or 0)
            except IndexError:
                weight = 0

            values.append(
                {
                    'priority': priority,
                    'weight': weight,
                    'port': port,
                    'target': target,
                }
            )

        yield 'SRV', name, ttl, values

    def _records_for_colon(self, zone, name, lines, arpa=False):
        # :fqdn:n:rdata:ttl:timestamp:lo
        # ANY

        if arpa:
            # no arpa
            return []

        if not zone.owns('SRV', name):
            # if name doesn't live under our zone there's nothing for us to do
            return

        # group by lines by the record type
        types = defaultdict(list)
        for line in lines:
            types[line[1].upper()].append(line)

        classes = Record.registered_types()
        for _type, lines in types.items():
            _class = classes.get(_type, None)
            if not _class:
                self.log.info(
                    '_records_for_colon: unrecognized type %s, %s', _type, line
                )
                continue

            ttl = self._ttl_for(lines, 3)

            rdatas = [l[2] for l in lines]
            yield _type, name, ttl, _class.parse_rdata_texts(rdatas)

    def _records_for_six(self, zone, name, lines, arpa=False):
        # 6fqdn:ip:ttl:timestamp:lo
        # AAAA (arpa False) & PTR (arpa True)
        if arpa:
            yield from self._records_for_caret(zone, name, lines, arpa)
        else:
            yield from self._records_for_three(zone, name, lines, arpa)

    SYMBOL_MAP = {
        '=': _records_for_equal,  # A
        '^': _records_for_caret,  # PTR
        '.': _records_for_dot,  # NS
        'C': _records_for_C,  # CNAME
        '+': _records_for_plus,  # A
        '@': _records_for_at,  # MX
        '&': _records_for_amp,  # NS
        '\'': _records_for_quote,  # TXT
        '3': _records_for_three,  # AAAA
        'S': _records_for_S,  # SRV
        ':': _records_for_colon,  # arbitrary
        '6': _records_for_six,  # AAAA
    }

    def _process_lines(self, zone, lines):
        data = defaultdict(lambda: defaultdict(list))
        for line in lines:
            symbol = line[0]

            # Skip type, remove trailing comments, and omit newline
            line = line[1:].split('#', 1)[0]
            # Split on :'s including :: and strip leading/trailing ws
            line = [p.strip() for p in line.split(':')]
            data[symbol][line[0]].append(line)

        return data

    def _process_symbols(self, zone, symbols, arpa):
        types = defaultdict(lambda: defaultdict(list))
        ttls = defaultdict(dict)
        for symbol, names in symbols.items():
            records_for = self.SYMBOL_MAP.get(symbol, None)
            if not records_for:
                # Something we don't care about
                self.log.info(
                    'skipping type %s, not supported/interested', symbol
                )
                continue

            for name, lines in names.items():
                for _type, name, ttl, values in records_for(
                    self, zone, name, lines, arpa=arpa
                ):
                    # remove the zone name
                    name = zone.hostname_from_fqdn(name)
                    types[_type][name].extend(values)
                    # first non-default wins, if we never see anything we'll
                    # just use the default below
                    if ttl != self.default_ttl:
                        ttls[_type][name] = ttl

        return types, ttls

    def populate(self, zone, target=False, lenient=False):
        self.log.debug(
            'populate: name=%s, target=%s, lenient=%s',
            zone.name,
            target,
            lenient,
        )

        before = len(zone.records)

        # This is complicate b/c the mapping between tinydns line types (called
        # symbols here) is not one to one with (octoDNS) records. Some lines
        # create multiple types of records and multiple lines are often combined
        # to make a single record (with multiple values.) Sometimes both happen.
        # To deal with this we'll do things in 3 stages:

        # first group lines by their symbol and name
        symbols = self._process_lines(zone, self._lines())

        # then work through those to group values by their _type and name
        zone_name = zone.name
        arpa = zone_name.endswith('in-addr.arpa.') or zone_name.endswith(
            'ip6.arpa.'
        )
        types, ttls = self._process_symbols(zone, symbols, arpa)

        # now we finally have all the values for each (soon to be) record
        # collected together, turn them into their coresponding record and add
        # it to the zone
        for _type, names in types.items():
            for name, values in names.items():
                data = {
                    'ttl': ttls[_type].get(name, self.default_ttl),
                    'type': _type,
                }
                if len(values) > 1:
                    data['values'] = _unique(values)
                else:
                    data['value'] = values[0]
                record = Record.new(zone, name, data, lenient=lenient)
                zone.add_record(record, lenient=lenient)

        self.log.info(
            'populate:   found %s records', len(zone.records) - before
        )


class TinyDnsFileSource(TinyDnsBaseSource):
    '''
    A basic TinyDNS zonefile importer created to import legacy data.

    tinydns:
        class: octodns.source.tinydns.TinyDnsFileSource
        # The location of the TinyDNS zone files
        directory: ./zones
        # The ttl to use for records when not specified in the data
        # (optional, default 3600)
        default_ttl: 3600

    NOTE: timestamps & lo fields are ignored if present.

    The source intends to conform to and fully support the official spec,
    https://cr.yp.to/djbdns/tinydns-data.html and the common patch/extensions to
    support IPv6 and a few other record types,
    https://docs.bytemark.co.uk/article/tinydns-format/.
    '''

    def __init__(self, id, directory, default_ttl=3600):
        self.log = logging.getLogger(f'TinyDnsFileSource[{id}]')
        self.log.debug(
            '__init__: id=%s, directory=%s, default_ttl=%d',
            id,
            directory,
            default_ttl,
        )
        super().__init__(id, default_ttl)
        self.directory = directory
        self._cache = None

    def _lines(self):
        if self._cache is None:
            # We unfortunately don't know where to look since tinydns stuff can
            # be defined anywhere so we'll just read all files
            lines = []
            for filename in listdir(self.directory):
                if filename[0] == '.':
                    # Ignore hidden files
                    continue
                with open(join(self.directory, filename), 'r') as fh:
                    lines += [l for l in fh.read().split('\n') if l]

            self._cache = lines

        return self._cache
