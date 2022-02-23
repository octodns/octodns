#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from collections import defaultdict
from os import listdir, makedirs
from os.path import isdir, isfile, join
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
        enforce_order: true
        # Whether duplicate records should replace rather than error
        # (optiona, default False)
        populate_should_replace: false

    Overriding values can be accomplished using multiple yaml providers in the
    `sources` list where subsequent providers have `populate_should_replace`
    set to `true`. An example use of this would be a zone that you want to push
    to external DNS providers and internally, but you want to modify some of
    the records in the internal version.

    config/octodns.com.yaml
    ---
    other:
      type: A
      values:
        - 192.30.252.115
        - 192.30.252.116
    www:
      type: A
      values:
        - 192.30.252.113
        - 192.30.252.114


    internal/octodns.com.yaml
    ---
    'www':
      type: A
      values:
        - 10.0.0.12
        - 10.0.0.13

    external.yaml
    ---
    providers:
      config:
        class: octodns.provider.yaml.YamlProvider
        directory: ./config

    zones:

      octodns.com.:
        sources:
          - config
        targets:
          - route53

    internal.yaml
    ---
    providers:
      config:
        class: octodns.provider.yaml.YamlProvider
        directory: ./config

      internal:
        class: octodns.provider.yaml.YamlProvider
        directory: ./internal
        populate_should_replace: true

    zones:

      octodns.com.:
        sources:
          - config
          - internal
        targets:
          - pdns

    You can then sync our records eternally with `--config-file=external.yaml`
    and internally (with the custom overrides) with
    `--config-file=internal.yaml`

    '''
    SUPPORTS_GEO = True
    SUPPORTS_DYNAMIC = True
    SUPPORTS_POOL_VALUE_STATUS = True
    SUPPORTS_MULTIVALUE_PTR = True
    SUPPORTS = set(('A', 'AAAA', 'ALIAS', 'CAA', 'CNAME', 'DNAME', 'LOC', 'MX',
                    'NAPTR', 'NS', 'PTR', 'SSHFP', 'SPF', 'SRV', 'TXT',
                    'URLFWD'))

    def __init__(self, id, directory, default_ttl=3600, enforce_order=True,
                 populate_should_replace=False, supports_root_ns=True,
                 *args, **kwargs):
        klass = self.__class__.__name__
        self.log = logging.getLogger(f'{klass}[{id}]')
        self.log.debug('__init__: id=%s, directory=%s, default_ttl=%d, '
                       'enforce_order=%d, populate_should_replace=%d',
                       id, directory, default_ttl, enforce_order,
                       populate_should_replace)
        super(YamlProvider, self).__init__(id, *args, **kwargs)
        self.directory = directory
        self.default_ttl = default_ttl
        self.enforce_order = enforce_order
        self.populate_should_replace = populate_should_replace
        self.supports_root_ns = supports_root_ns

    @property
    def SUPPORTS_ROOT_NS(self):
        return self.supports_root_ns

    def _populate_from_file(self, filename, zone, lenient):
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
                        zone.add_record(record, lenient=lenient,
                                        replace=self.populate_should_replace)
            self.log.debug('_populate_from_file: successfully loaded "%s"',
                           filename)

    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s, target=%s, lenient=%s', zone.name,
                       target, lenient)

        if target:
            # When acting as a target we ignore any existing records so that we
            # create a completely new copy
            return False

        before = len(zone.records)
        filename = join(self.directory, f'{zone.name}yaml')
        self._populate_from_file(filename, zone, lenient)

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
            if record._octodns:
                d['octodns'] = record._octodns
            data[record.name].append(d)

        # Flatten single element lists
        for k in data.keys():
            if len(data[k]) == 1:
                data[k] = data[k][0]

        if not isdir(self.directory):
            makedirs(self.directory)

        self._do_apply(desired, data)

    def _do_apply(self, desired, data):
        filename = join(self.directory, f'{desired.name}yaml')
        self.log.debug('_apply:   writing filename=%s', filename)
        with open(filename, 'w') as fh:
            safe_dump(dict(data), fh)


def _list_all_yaml_files(directory):
    yaml_files = set()
    for f in listdir(directory):
        filename = join(directory, f)
        if f.endswith('.yaml') and isfile(filename):
            yaml_files.add(filename)
    return list(yaml_files)


class SplitYamlProvider(YamlProvider):
    '''
    Core provider for records configured in multiple YAML files on disk.

    Behaves mostly similarly to YamlConfig, but interacts with multiple YAML
    files, instead of a single monolitic one. All files are stored in a
    subdirectory matching the name of the zone (including the trailing .) of
    the directory config. The files are named RECORD.yaml, except for any
    record which cannot be represented easily as a file; these are stored in
    the catchall file, which is a YAML file the zone name, prepended with '$'.
    For example, a zone, 'github.com.' would have a catch-all file named
    '$github.com.yaml'.

    A full directory structure for the zone github.com. managed under directory
    "zones/" would be:

    zones/
      github.com./
        $github.com.yaml
        www.yaml
        ...

    config:
        class: octodns.provider.yaml.SplitYamlProvider
        # The location of yaml config files (required)
        directory: ./config
        # The ttl to use for records when not specified in the data
        # (optional, default 3600)
        default_ttl: 3600
        # Whether or not to enforce sorting order on the yaml config
        # (optional, default True)
        enforce_order: True
    '''

    # Any record name added to this set will be included in the catch-all file,
    # instead of a file matching the record name.
    CATCHALL_RECORD_NAMES = ('*', '')

    def __init__(self, id, directory, extension='.', *args, **kwargs):
        super(SplitYamlProvider, self).__init__(id, directory, *args, **kwargs)
        self.extension = extension

    def _zone_directory(self, zone):
        filename = f'{zone.name[:-1]}{self.extension}'
        return join(self.directory, filename)

    def populate(self, zone, target=False, lenient=False):
        self.log.debug('populate: name=%s, target=%s, lenient=%s', zone.name,
                       target, lenient)

        if target:
            # When acting as a target we ignore any existing records so that we
            # create a completely new copy
            return False

        before = len(zone.records)
        yaml_filenames = _list_all_yaml_files(self._zone_directory(zone))
        self.log.info('populate:   found %s YAML files', len(yaml_filenames))
        for yaml_filename in yaml_filenames:
            self._populate_from_file(yaml_filename, zone, lenient)

        self.log.info('populate:   found %s records, exists=False',
                      len(zone.records) - before)
        return False

    def _do_apply(self, desired, data):
        zone_dir = self._zone_directory(desired)
        if not isdir(zone_dir):
            makedirs(zone_dir)

        catchall = dict()
        for record, config in data.items():
            if record in self.CATCHALL_RECORD_NAMES:
                catchall[record] = config
                continue
            filename = join(zone_dir, f'{record}.yaml')
            self.log.debug('_apply:   writing filename=%s', filename)
            with open(filename, 'w') as fh:
                record_data = {record: config}
                safe_dump(record_data, fh)
        if catchall:
            # Scrub the trailing . to make filenames more sane.
            dname = desired.name[:-1]
            filename = join(zone_dir, f'${dname}.yaml')
            self.log.debug('_apply:   writing catchall filename=%s', filename)
            with open(filename, 'w') as fh:
                safe_dump(catchall, fh)
