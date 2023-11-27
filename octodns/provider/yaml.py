#
#
#

import logging
from collections import defaultdict
from os import listdir, makedirs
from os.path import isdir, isfile, join

from ..deprecation import deprecated
from ..record import Record
from ..yaml import safe_dump, safe_load
from . import ProviderException
from .base import BaseProvider


class YamlProvider(BaseProvider):
    '''
    Core provider for records configured in yaml files on disk.

    config:
        class: octodns.provider.yaml.YamlProvider

        # The location of yaml config files. By default records are defined in a
        # file named for the zone in this directory, the zone file, e.g.
        # something.com.yaml.
        # (required)
        directory: ./config

        # The ttl to use for records when not specified in the data
        # (optional, default 3600)
        default_ttl: 3600

        # Whether or not to enforce sorting order when loading yaml
        # (optional, default True)
        enforce_order: true

        # Whether duplicate records should replace rather than error
        # (optional, default False)
        populate_should_replace: false

        # The file extension used when loading split style zones, Null means
        # disabled. When enabled the provider will search for zone records split
        # across multiple YAML files in the directory with split_extension
        # appended to the zone name, See "Split Details" below.
        # split_extension should include the "."
        # (optional, default null, "." is the recommended best practice when
        # enabling)
        split_extension: null

        # When writing YAML records out to disk with split_extension enabled
        # each record is written out into its own file with .yaml appended to
        # the name of the record. The two exceptions are for the root and
        # wildcard nodes. These records are written into a file named
        # `$[zone.name].yaml`. If you would prefer this catchall file not be
        # used `split_catchall` can be set to False to instead write those
        # records out to `.yaml` and `*.yaml` respectively. Note that some
        # operating systems may not allow files with those names.
        # (optional, default True)
        split_catchall: true

        # Optional filename with record data to be included in all zones
        # populated by this provider. Has no effect when used as a target.
        # (optional, default null)
        shared_filename: null

        # Disable loading of the zone .yaml files.
        # (optional, default False)
        disable_zonefile: false

    Split Details
    -------------

    All files are stored in a subdirectory matching the name of the zone
    (including the trailing .) of the directory config. It is a recommended
    best practice that the files be named RECORD.yaml, but all files are
    sourced and processed ignoring the filenames so it is up to you how to
    organize them.

    With `split_extension: .` the directory structure for the zone github.com.
    managed under directory "zones/" would look like:

    zones/
      github.com./
        $github.com.yaml
        www.yaml
        ...

    Overriding Values
    -----------------

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
    SUPPORTS_DYNAMIC_SUBNETS = True
    SUPPORTS_MULTIVALUE_PTR = True

    # Any record name added to this set will be included in the catch-all file,
    # instead of a file matching the record name.
    CATCHALL_RECORD_NAMES = ('*', '')

    def __init__(
        self,
        id,
        directory,
        default_ttl=3600,
        enforce_order=True,
        populate_should_replace=False,
        supports_root_ns=True,
        split_extension=False,
        split_catchall=True,
        shared_filename=False,
        disable_zonefile=False,
        *args,
        **kwargs,
    ):
        klass = self.__class__.__name__
        self.log = logging.getLogger(f'{klass}[{id}]')
        self.log.debug(
            '__init__: id=%s, directory=%s, default_ttl=%d, enforce_order=%d, populate_should_replace=%s, supports_root_ns=%s, split_extension=%s, split_catchall=%s, shared_filename=%s, disable_zonefile=%s',
            id,
            directory,
            default_ttl,
            enforce_order,
            populate_should_replace,
            supports_root_ns,
            split_extension,
            split_catchall,
            shared_filename,
            disable_zonefile,
        )
        super().__init__(id, *args, **kwargs)
        self.directory = directory
        self.default_ttl = default_ttl
        self.enforce_order = enforce_order
        self.populate_should_replace = populate_should_replace
        self.supports_root_ns = supports_root_ns
        self.split_extension = split_extension
        self.split_catchall = split_catchall
        self.shared_filename = shared_filename
        self.disable_zonefile = disable_zonefile

    def copy(self):
        kwargs = dict(self.__dict__)
        kwargs['id'] = f'{kwargs["id"]}-copy'
        del kwargs['log']
        return YamlProvider(**kwargs)

    @property
    def SUPPORTS(self):
        # The yaml provider supports all record types even those defined by 3rd
        # party modules that we know nothing about, thus we dynamically return
        # the types list that is registered in Record, everything that's know as
        # of the point in time we're asked
        return set(Record.registered_types().keys())

    def supports(self, record):
        # We're overriding this as a performance tweak, namely to avoid calling
        # the implementation of the SUPPORTS property to create a set from a
        # dict_keys every single time something checked whether we support a
        # record, the answer is always yes so that's overkill and we can just
        # return True here and be done with it
        return True

    @property
    def SUPPORTS_ROOT_NS(self):
        return self.supports_root_ns

    def list_zones(self):
        self.log.debug('list_zones:')
        zones = set()

        extension = self.split_extension
        if extension:
            # we want to leave the .
            trim = len(extension) - 1
            self.log.debug(
                'list_zones:   looking for split zones, trim=%d', trim
            )
            for dirname in listdir(self.directory):
                not_ends_with = not dirname.endswith(extension)
                not_dir = not isdir(join(self.directory, dirname))
                if not_dir or not_ends_with:
                    continue
                if trim:
                    dirname = dirname[:-trim]
                zones.add(dirname)

        if not self.disable_zonefile:
            self.log.debug('list_zones:   looking for zone files')
            for filename in listdir(self.directory):
                not_ends_with = not filename.endswith('.yaml')
                too_few_dots = filename.count('.') < 2
                not_file = not isfile(join(self.directory, filename))
                if not_file or not_ends_with or too_few_dots:
                    continue
                # trim off the yaml, leave the .
                zones.add(filename[:-4])

        return sorted(zones)

    def _split_sources(self, zone):
        ext = self.split_extension
        utf8 = join(self.directory, f'{zone.decoded_name[:-1]}{ext}')
        idna = join(self.directory, f'{zone.name[:-1]}{ext}')
        directory = None
        if isdir(utf8):
            if utf8 != idna and isdir(idna):
                raise ProviderException(
                    f'Both UTF-8 "{utf8}" and IDNA "{idna}" exist for {zone.decoded_name}'
                )
            directory = utf8
        elif isdir(idna):
            directory = idna
        else:
            return []

        for filename in listdir(directory):
            if filename.endswith('.yaml'):
                yield join(directory, filename)

    def _zone_sources(self, zone):
        utf8 = join(self.directory, f'{zone.decoded_name}yaml')
        idna = join(self.directory, f'{zone.name}yaml')
        if isfile(utf8):
            if utf8 != idna and isfile(idna):
                raise ProviderException(
                    f'Both UTF-8 "{utf8}" and IDNA "{idna}" exist for {zone.decoded_name}'
                )
            return utf8
        elif isfile(idna):
            return idna

        return None

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
                        record = Record.new(
                            zone, name, d, source=self, lenient=lenient
                        )
                        zone.add_record(
                            record,
                            lenient=lenient,
                            replace=self.populate_should_replace,
                        )
            self.log.debug(
                '_populate_from_file: successfully loaded "%s"', filename
            )

    def populate(self, zone, target=False, lenient=False):
        self.log.debug(
            'populate: name=%s, target=%s, lenient=%s',
            zone.decoded_name,
            target,
            lenient,
        )

        if target:
            # When acting as a target we ignore any existing records so that we
            # create a completely new copy
            return False

        before = len(zone.records)

        sources = []

        split_extension = self.split_extension
        if split_extension:
            sources.extend(self._split_sources(zone))

        if not self.disable_zonefile:
            source = self._zone_sources(zone)
            if source:
                sources.append(source)

        if self.shared_filename:
            sources.append(join(self.directory, self.shared_filename))

        if not sources:
            raise ProviderException(f'no YAMLs found for {zone.decoded_name}')

        # determinstically order our sources
        sources.sort()

        for source in sources:
            self._populate_from_file(source, zone, lenient)

        self.log.info(
            'populate:   found %s records, exists=False',
            len(zone.records) - before,
        )
        return False

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        self.log.debug(
            '_apply: zone=%s, len(changes)=%d',
            desired.decoded_name,
            len(changes),
        )
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
            # we want to output the utf-8 version of the name
            data[record.decoded_name].append(d)

        # Flatten single element lists
        for k in data.keys():
            if len(data[k]) == 1:
                data[k] = data[k][0]

        if not isdir(self.directory):
            self.log.debug('_apply: creating directory=%s', self.directory)
            makedirs(self.directory)

        if self.split_extension:
            # we're going to do split files
            decoded_name = desired.decoded_name[:-1]
            directory = join(
                self.directory, f'{decoded_name}{self.split_extension}'
            )

            if not isdir(directory):
                self.log.debug('_apply: creating split directory=%s', directory)
                makedirs(directory)

            catchall = {}
            for record, config in data.items():
                if self.split_catchall and record in self.CATCHALL_RECORD_NAMES:
                    catchall[record] = config
                    continue
                filename = join(directory, f'{record}.yaml')
                self.log.debug('_apply:   writing filename=%s', filename)

                with open(filename, 'w') as fh:
                    record_data = {record: config}
                    safe_dump(record_data, fh)

            if catchall:
                # Scrub the trailing . to make filenames more sane.
                filename = join(directory, f'${decoded_name}.yaml')
                self.log.debug(
                    '_apply:   writing catchall filename=%s', filename
                )
                with open(filename, 'w') as fh:
                    safe_dump(catchall, fh)

        else:
            # single large file
            filename = join(self.directory, f'{desired.decoded_name}yaml')
            self.log.debug('_apply:   writing filename=%s', filename)
            with open(filename, 'w') as fh:
                safe_dump(dict(data), fh, allow_unicode=True)


class SplitYamlProvider(YamlProvider):
    '''
    DEPRECATED: Use YamlProvider with the split_extension parameter instead.

    When migrating the following configuration options would result in the same
    behavior as SplitYamlProvider

       config:
         class: octodns.provider.yaml.YamlProvider
         # extension is configured as split_extension
         split_extension: .
         split_catchall: true
         disable_zonefile: true

    TO BE REMOVED: 2.0
    '''

    def __init__(self, id, directory, *args, extension='.', **kwargs):
        kwargs.update(
            {
                'split_extension': extension,
                'split_catchall': True,
                'disable_zonefile': True,
            }
        )
        super().__init__(id, directory, *args, **kwargs)
        deprecated(
            'SplitYamlProvider is DEPRECATED, use YamlProvider with split_extension, split_catchall, and disable_zonefile instead, will go away in v2.0',
            stacklevel=99,
        )
