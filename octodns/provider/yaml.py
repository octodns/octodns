#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from collections import defaultdict
from os import makedirs
from os.path import isdir, join
import logging

from ..record import Record
from ..yaml import safe_load, safe_dump
from .base import BaseProvider


class YamlProvider(BaseProvider):
    '''
    Core provider for records configured in yaml files on disk.

    config:
        class: octodns.provider.yaml.YamlProvider
        # The location of yaml config files (required)
        directory: ./config
        # The ttl to use for records when not specified in the data
        # (optional, default 3600)
        default_ttl: 3600
        # Whether or not to enforce sorting order on the yaml config
        # (optional, default True)
        enforce_order: True
    '''
    SUPPORTS_GEO = True
    SUPPORTS = set(('A', 'AAAA', 'ALIAS', 'CAA', 'CNAME', 'MX', 'NAPTR', 'NS',
                    'PTR', 'SSHFP', 'SPF', 'SRV', 'TXT'))

    def __init__(self, id, directory, default_ttl=3600, enforce_order=True,
                 *args, **kwargs):
        self.log = logging.getLogger('YamlProvider[{}]'.format(id))
        self.log.debug('__init__: id=%s, directory=%s, default_ttl=%d, '
                       'enforce_order=%d', id, directory, default_ttl,
                       enforce_order)
        super(YamlProvider, self).__init__(id, *args, **kwargs)
        self.directory = directory
        self.default_ttl = default_ttl
        self.enforce_order = enforce_order

    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s, target=%s, lenient=%s', zone.name,
                       target, lenient)

        if target:
            # When acting as a target we ignore any existing records so that we
            # create a completely new copy
            return False

        before = len(zone.records)
        filename = join(self.directory, '{}yaml'.format(zone.name))
        with open(filename, 'r') as fh:
            yaml_data = safe_load(fh, enforce_order=self.enforce_order)
            if yaml_data:
                for name, data in yaml_data.items():
                    if not isinstance(data, list):
                        data = [data]
                    for d in data:
                        if 'ttl' not in d:
                            d['ttl'] = self.default_ttl
                        record = Record.new(zone, name, d, source=self,
                                            lenient=lenient)
                        zone.add_record(record)

        self.log.info('populate:   found %s records, exists=False',
                      len(zone.records) - before)
        return False

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        self.log.debug('_apply: zone=%s, len(changes)=%d', desired.name,
                       len(changes))
        # Since we don't have existing we'll only see creates
        records = [c.new for c in changes]
        # Order things alphabetically (records sort that way
        records.sort()
        data = defaultdict(list)
        for record in records:
            d = record.data
            d['type'] = record._type
            if record.ttl == self.default_ttl:
                # ttl is the default, we don't need to store it
                del d['ttl']
            data[record.name].append(d)

        # Flatten single element lists
        for k in data.keys():
            if len(data[k]) == 1:
                data[k] = data[k][0]

        if not isdir(self.directory):
            makedirs(self.directory)

        filename = join(self.directory, '{}yaml'.format(desired.name))
        self.log.debug('_apply:   writing filename=%s', filename)
        with open(filename, 'w') as fh:
            safe_dump(dict(data), fh)
