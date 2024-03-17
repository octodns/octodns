## v1.6.1 - 2024-03-17 - Didn't we do this already

* Fix env var type handling that was previously fixed in 1.5.1 and then
  regressed in 1.6.0.

## v1.6.0 - 2024-03-11 - It's a secret, if I told you I'd have to kill you

* Add EnsureTrailingDots processor
* Beta support for custom secret providers added to Manager.

## v1.5.1 - 2024-03-08 - env/* type conversion fix

* Improved env variable to parameter type conversion logic, avoid converting
  all numbers to float which caused some formatting issues in things that
  weren't being careful enough.

## v1.5.0 - 2024-02-26 - Checksums, nested expansion, & flexable values

* Beta support for Manager.enable_checksum and octodns-sync --checksum Allows a
  safer plan & apply workflow where the apply only moves forward if the apply
  phase plan exactly matches the previous round's planning.
* Fix for bug in MetaProcessor _up_to_date check that was failing when there was
  a plan with a single change type with a single value, e.g. CNAME.
* Support added for config env variable expansion on nested levels, not just
  top-level provider/processor keys
* _ChunkedValue ASCII validation added, SPF & TXT
* Re-work value/values handling to always try and do the "right" thing based on
  the content, so both singular values and lists will be handled identically
  regardless of whether the key is value or values. This may result in
  changes/fixes on the first sync after updating IFF you currently have
  `values: a-single-thing`, which would have previously been pushed up as bunch
  of single character values.
* Record.octodns added to formally make that data "API" and Record._octodns is
  deprecated. The latter has been converted to properties that return the
  former and emit deprecation warnings.

## v1.4.0 - 2023-12-04 - Minor Meta

* Record.lenient property added similar to other common/standard _octodns data
* Processor.process_source_and_target_zones added to support modifying both the
  desired and/or existing zones just prior to computing changes.
* Fix bug with Record.copy when values is an empty list []
* Fix an issue in MetaProcessor/Manager.include_meta where include_provider
  wasn't correctly taking effect

## v1.3.0 - 2023-11-14 - New and improved processors

#### Noteworthy changes

* Added `octodns.__version__` to replace `octodns.__VERSION__` as the former is
  more of a standard, per pep-8. `__VERSION__` is deprecated and will go away
  in 2.x
* Fixed issues with handling of chunking large TXT values for providers that use
  the in-built `rrs` method
* Removed code that included sha in module version number when installing from
  repo as it caused problems with non-binary installs.
* Fixed a bug/shortcoming in Record.data where it didn't include the `octodns`
  portion of the record's data. Record.copy also omitted it since it relies on
  .data for the heavy lifting. There are no known actual problems due to this
  bug, but it's possible (non-public) third party providers are susceptible. The
  most likely place to hit issues in is tests where data and/or copy are abused.

#### Stuff

* Added ZoneNameFilter processor to enable ignoring/alerting on type-os like
  octodns.com.octodns.com
* NetworkValueAllowlistFilter/NetworkValueRejectlistFilter added to
  processors.filter to enable filtering A/AAAA records based on value. Can be
  useful if you have records with non-routable values in an internal copy of a
  zone, but want to exclude them when pushing the same zone publically (split
  horizon)
* ExcludeRootNsChanges processor that will error (or warn) if plan includes a
  change to root NS records
* Include the octodns special section info in `Record.__repr__`, makes it easier
  to debug things with providers that have special functionality configured
  there.
* Most processor.filter processors now support an include_target flag that can
  be set to False to leave the target zone data untouched, thus remove any
  existing filtered records. Default behavior is unchanged and filtered records
  will be completely invisible to octoDNS

## v1.2.1 - 2023-09-29 - Now with fewer stale files

* Update script/release to do clean room dist builds

## v1.2.0 - 2023-09-28 - Bunch more bug fixes

* Record.from_rrs supports `source` parameter
* Record.parse_rdata_text unquotes any quoted (string) values
* Fix crash bug when using the YamlProvider with a directory that contains a
  mix of split and non-split zone yamls. See https://github.com/octodns/octodns/issues/1066
* Fix discovery of zones from different sources when there are multiple dynamic
  zones. See https://github.com/octodns/octodns/issues/1068

## v1.1.1 - 2023-09-16 - Doh! Fix that one little thing

* Address a bug in the handling of loading auto-arpa manager configuration.

## v1.1.0 - 2023-09-13 - More than enough for a minor release

#### Noteworthy changes

* New dynamic zone config support that allows wildcard entries in the octoDNS
  config to be expanded by the source provider(s). See
  [Dynamic Zone Config](/README.md#dynamic-zone-config) for more information.
* SplitYamlProvider has been deprecated and will be removed in 2.0. YamlProvider
  now includes the ability to process split zones when configured to do so and
  allows for more flexibility in how things are laid out than was previously
  possible. This includes the ability to split some zones and not others and
  even to have partially split zones with some records in the primary zone YAML
  and others in a split directory. See YamlProvider documentation for more info.
* YamlProvider now supports a `shared_filename` that can be used to add a set of
  common records across all zones using the provider. It can be used stand-alone
  or in combination with zone files and/or split configs to aid in DRYing up DNS
* YamlProvider now supports an `!include` directive which enables shared
  snippets of config to be reused across many records, e.g. common dynamic rules
  across a set of services with service-specific pool values or a unified SFP
  value included in TXT records at the root of all zones.
* SpfRecord is formally deprecated with an warning and will become a
  ValidationError in 2.x
* SpfDnsLookupProcessor is formally deprcated in favor of the version relocated
  into https://github.com/octodns/octodns-spf and will be removed in 2.x
* MetaProcessor added to enable some useful/cool options for debugging/tracking
  DNS changes. Specifically timestamps/uuid so you can track whether changes
  that have been pushed to providers have propogated/transferred correctly.

#### Stuff

* Add context to general configuration and Record validation, e.g.
  Some problem at filename.yaml, line 42, column 14. Our custom Yaml Loaders
  attach this context information, arbitrary string. Other providers may do so
  by creating ContextDict to pass as `data` into Record.new.
* Add --all option to octodns-validate to enable showing all record validation
  errors (as warnings) rather than exiting on the first. Exit code is non-zero
  when there are any validation errors.
* New `post_processors` manager configuration parameter to add global processors
  that run AFTER zone-specific processors. This should allow more complete
  control over when processors are run.

## v1.0.0 - 2023-07-30 - The One

1.0 marks a point at which we can formally deprecate things that will be
going away with 2.0 more than specific functionality that has been added or
having reached a notable level of stability (beyond what is normal.) It is also
long (years) overdue.

#### Noteworthy changes

* `geo` records are deprecated.

#### Stuff

* Removal of a Python 3.7 specific import work-around now that it's no longer an
  active/supported version. Also bumps required minimum version of Python 3.8

## v1.0.0.rc1 - 2023-07-20 - The last one before the 1s

* Record and Zone validation now ensures there's no whitespace in names
* OwnershipProcessor managed records always add w/lenient=True, this allows
  ownership to be marked in the same zone for delegation NS records.
* octodns-report access --lenient flag to allow running reports with records
  sourced from providers with non-compliant record data.
* Correctly handle FQDNs in TinyDNS config files that end with trailing .'s
* Complete rewrite of TinyDnsBaseSource to fully implement the spec and the ipv6
  extensions

## v1.0.0.rc0 - 2023-05-16 - First of the ones

#### Noteworthy changes

* 1.x Deprecation removals
   * Provider, Source, and Processor shims removed, they've been warnings for >
     1yr.  Everything should be using and referring to provider-specific
     modules now.
   * Provider.strict_supports defaults to true, can be returned to the old
     behavior by setting strict_supports=False in your provider params.
* octodns.record has been broken up into multiple files/modules. Most of the
  primary things that were available at that module path still will be, but if
  you are importing things like idna_encode/decode that actually live elsewhere
  from octodns.record you'll need to update and pull them from their actual
  home. Classes beginning with _ are not exported from octodns.record any
  longer as they were considered private/protected.
* Beta support for auto-arpa has been added, See the
  [auto-arpa documentation](/docs/auto_arpa.md) for more information.
* Support for subnet targeting in dynamic records, see
  [this section](/docs/dynamic_records.md#subnets) of dynamic records
  documentation for more information.
* Enhanced validations on dynamic rules to encourage best practices
   * The last rule must be a catch-all w/o any targeted geos or subnets
   * Geos must not be repeated in multiple rules
   * Geos in rules and subsequent rules must be ordered most to least specific,
     e.g. NA-US-TN must come before NA-US, which must occur before NA
   * Similarly, subnets must not be repeated in multiple rules, and various
     subnet rules must be ordered such that most specific subnets appear before
     less specific ones; e.g. 10.1.1.0/24 must appear before 10.1.0.0/16.
   * Subnet targeting is considered to be more specific than geo targeting, so
     subnet-only rules must appear before any subnet+geo rules, followed by
     geo-only rules (and catch-all rule w/o any geos/subnets in the end)

#### Stuff

* Added new DsRecord type (provider support will be added over time)
* Added simple IgnoreRootNsFilter
* Minor refactor on YamlProvider to add get_filenames making it a bit easier to
  create specialized providers inheriting from it
* Fixed bug in OwnershipProcessor when all changes were removed from plans

## v0.9.21 - 2022-10-16 - Last of the oughts

* Shim AxfrSource and ZoneFileSource post extraction into
  https://github.com/octodns/octodns-bind

## v0.9.20 - 2022-10-05 - International friendly

#### Noteworthy changes

* Added support for automatic handling of IDNA (utf-8) zones. Everything is
  stored IDNA encoded internally. For ASCII zones that's a noop. For zones with
  utf-8 chars they will be converted and all internals/providers will see the
  encoded version and work with it without any knowledge of it having been
  converted. This means that all providers will automatically support IDNA as of
  this version. IDNA zones will generally be displayed in the logs in their
  decoded form. Both forms should be accepted in command line arguments.
  Providers may need to be updated to display the decoded form in their logs,
  until then they'd display the IDNA version.
* IDNA value support for Record types that hold FQDNs: ALIAS, CNAME, DNAME, PTR,
  MX, NS, and SRV.
* Support for configuring global processors that apply to all zones with
  `manager.processors`

#### Stuff

* Addressed shortcomings with YamlProvider.SUPPORTS in that it didn't include
  dynamically registered types, was a static list that could have drifted over
  time even ignoring 3rd party types.
* Provider._process_desired_zone needed to call Provider.supports rather than
  doing it's own `_type in provider.SUPPORTS`. The default behavior in
  Source.supports is ^, but it's possible for providers to override that
  behavior and do special checking and `_process_desired_zone` wasn't taking
  that into account.
* Now that it's used as it needed to be YamlProvider overrides
  Provider.supports and just always says Yes so that any dynamically registered
  types will be supported.
* Add TtlRestrictionFilter processor for adding ttl restriction/checking
* NameAllowlistFilter & NameRejectlistFilter implementations to support
  filtering on record names to include/exclude records from management.
* All Record values are now first class objects. This shouldn't be an externally
  visible change, but will enable future improvements.
* --quiet command line option added to raise log level to WARNING, plan
  output now comes from `plan` logger rather than `Manager` so that it can stay
  at info
* --logging-config command line option added to allow complete logging config
  customization, see
  https://docs.python.org/3/library/logging.config.html#logging-config-dictschema
  for file format and
  https://github.com/octodns/octodns/pull/945#issuecomment-1262839550 for an
  example config

## v0.9.19 - 2022-08-14 - Subzone handling

* Fixed issue with sub-zone handling introduced in 0.9.18

## v0.9.18 - 2022-08-09 - Internationalization

* Added octodns.idna idna_encode/idna_decode helpers, providers will need to
  individually add support via these helpers though :-/
* `black` formatting implemented (including .git-blame-ignore-revs)
* --output-provider support for dump to allow configurable dump
  formatting/details
* TLSA record type support
* Subzones support for skipping levels

## v0.9.17 - 2022-04-02 - Registration required

#### Noteworthy changes

* The changes in plans are now ordered based on change type prior to
  considering the record name and type as was previously done. The chosen
  order is: deletes, creates, updates. The reason for that many providers make
  changes one at a time. When changing the type of a record, e.g. from A to
  CNAME of vice versa this is done by deleting the old and creating the new.
  If the CNAME create happens before the A delete it will often violate
  rules against having typed records live at the same node as a CNAME. Several
  providers have always handled this by sorting the changes themselves. This
  just standardizes what they are doing as many other providers appear to need
  to do so, but weren't. There was an ordering before, but it was essentially
  arbitrarily picked.
* Record.register_type added so that providers can register custom record
  types, see [docs/records.md](docs/records.md) for more information
* New `octodns-versions` command which will log out the version of octodns and
  any provider/processor/plan_output modules you are using.

#### Stuff

* Manager includes the octoDNS version in its init log line
* Non-official release installs will now include a bit of the sha to indicate
  specifically what revision is being used, e.g. 0.9.17+abcdef12, these roughly
  follow PEP440 guidelines

## v0.9.16 - 2022-03-04 - Manage the root of the problem

#### Noteworthy changes

* Foundational support for root NS record management.
   * YamlProvider has it enabled and in general everyone should add root NS
     records that match what is in their provider(s) as of this release if they
     aren't already there.
   * Other providers will add root NS support over time following this release
     once they have had the chance to investigate the functionality and
     implement management if possible with whatever accomidations are required.
   * Watch your providers README.md and CHANGELOG.md for support and more
     information.
   * Root NS record changes will always require `--force` indicating that they
     are impactful changes that need a careful :eyes:

#### Stuff

* _AggregateTarget has more complete handling of SUPPORTS* functionality,
  mostly applicable for the compare operation.
* Fix null MX record validation error introduced in 0.9.15, `.` is again
  allowed as a valid `exchange` value.

## v0.9.15 - 2022-02-07 - Where have all the providers gone?

#### Noteworthy changes

* Providers extracted from octoDNS core into individual repos
  https://github.com/octodns/octodns/issues/622 &
  https://github.com/octodns/octodns/pull/822 for more information.
   * [AzureProvider](https://github.com/octodns/octodns-azure/)
   * [AkamaiProvider](https://github.com/octodns/octodns-edgedns/)
   * [CloudflareProvider](https://github.com/octodns/octodns-cloudflare/)
   * [ConstellixProvider](https://github.com/octodns/octodns-constellix/)
   * [DigitalOceanProvider](https://github.com/octodns/octodns-digitalocean/)
   * [DnsimpleProvider](https://github.com/octodns/octodns-dnsimple/)
   * [DnsMadeEasyProvider](https://github.com/octodns/octodns-dnsmadeeasy/)
   * [DynProvider](https://github.com/octodns/octodns-dynprovider/)
   * [EasyDnsProvider](https://github.com/octodns/octodns-easydns/)
   * [EtcHostsProvider](https://github.com/octodns/octodns-etchosts/)
   * [GandiProvider](https://github.com/octodns/octodns-gandi/)
   * [GcoreProvider](https://github.com/octodns/octodns-gcore/)
   * [GoogleCloudProvider](https://github.com/octodns/octodns-googlecloud/)
   * [HetznerProvider](https://github.com/octodns/octodns-hetzner/)
   * [MythicBeastsProvider](https://github.com/octodns/octodns-mythicbeasts/)
   * [Ns1Provider](https://github.com/octodns/octodns-ns1/)
   * [OvhProvider](https://github.com/octodns/octodns-ovh/)
   * [PowerDnsProvider](https://github.com/octodns/octodns-powerdns/)
   * [RackspaceProvider](https://github.com/octodns/octodns-rackspace/)
   * [Route53Provider](https://github.com/octodns/octodns-route53/) also
     AwsAcmMangingProcessor
   * [SelectelProvider](https://github.com/octodns/octodns-selectel/)
   * [TransipProvider](https://github.com/octodns/octodns-transip/)
   * [UltraDnsProvider](https://github.com/octodns/octodns-ultradns/)
* As part of the extraction work octoDNS's requirements (setup.py and .txt
  files) have been updated and minimized and a helper script,
  script/update-requirements has been added to help manage the txt files going
  forward.

#### Prior to extraction

* NS1 provider has received improvements to the dynamic record implementation.
  As a result, if octoDNS is downgraded from this version, any dynamic records
  created or updated using this version will show an update.
* An edge-case bug related to geo rules involving continents in NS1 provider
  has been fixed in this version. However, it will not show/fix the records that
  match this edge-case. See https://github.com/octodns/octodns/pull/809 for
  more information. If octoDNS is downgraded from this version, any dynamic
  records created or updated using this version and matching the said edge-case
  will not be read/parsed correctly by the older version and will show a diff.
* Transip was updated to their new client api

#### Stuff

* Additional FQDN validation to ALIAS/CNAME value, MX exchange, SRV target and
  tests of the functionality.
* Improvements around dynamic record value weights allowing finer grained
  control

## v0.9.14 - 2021-10-10 - A new supports system

#### Noteworthy changes

* Provider `strict_supports` param added, currently defaults to `false`, along
  with Provider._process_desired_zone this forms the foundations of a new
  "supports" system where providers will warn or error (depending on the value
  of `strict_supports`) during planning about their inability to do what
  they're being asked. When `false` they will warn and "adjust" the desired
  records. When true they will abort with an error indicating the problem. Over
  time it is expected that all "supports" checking/handling will move into this
  paradigm and `strict_supports` will likely be changed to default to `true`.
* Zone shallow copy support, reworking of Processors (alpha) semantics
* NS1 NA target now includes `SX` and `UM`. If `NA` continent is in use in
  dynamic records care must be taken to upgrade/downgrade to v0.9.13.
* Ns1Provider now supports a new parameter, shared_notifylist, which results in
  all dynamic record monitors using a shared notify list named 'octoDNS NS1
  Notify List'. Only newly created record values will use the shared notify
  list. It should be safe to enable this functionality, but existing records
  will not be converted. Note: Once this option is enabled downgrades to
  previous versions of octoDNS are discouraged and may result in undefined
  behavior and broken records. See https://github.com/octodns/octodns/pull/749
  for related discussion.
* TransipProvider removed as it currently relies on `suds` which is broken in
  new python versions and hasn't seen a release since 2010. May return with
  https://github.com/octodns/octodns/pull/762

#### Stuff

* Fully remove python 2.7 support & sims
* Dynamic record pool status flag: up/down/obey added w/provider support as
  possible.
* Support for multi-value PTRs where providers allow them
* Normalize IPv6 addresses to avoid false changes and simplify providers
* Include pure-python wheel distirubtions in release builds
* Improvements and updates to AzureProvider, especially w/respect to dynamic
  records.
* NS1Provider support for IPv6 monitors and general caching/performance
  improvements
* Route53Provider.get_zones_by_name option to avoid paging through huge lists
  and hitting rate limits
* Misc Route53Provider
* Ensure no network access during testing (helps with runtime)
* Sped up the long pole unit tests
* Misc. ConstellixProvider, DigitalOceanProvider, GCoreProvider, and
  Route53Provider fixes & improvements

## v0.9.13 - 2021-07-18 - Processors Alpha

#### Noteworthy changes

* Alpha support for Processors has been added. Processors allow for hooking
  into the source, target, and planing process to make nearly arbitrary changes
  to data. See the [octodns/processor/](/octodns/processor) directory for
  examples. The change has been designed to have no impact on the process
  unless the `processors` key is present in zone configs.
* Fixes NS1 provider's geotarget limitation of using `NA` continent. Now, when
  `NA` is used in geos it considers **all** the countries of `North America`
  instead of just `us-east`, `us-west` and `us-central` regions
* `SX' &amp; 'UM` country support added to NS1Provider, not yet in the North
   America list for backwards compatibility reasons. They will be added in the
   next releaser.

#### Stuff

* Lots of progress on the partial/beta support for dynamic records in Azure,
  still not production ready.
* NS1 fix for when a pool only exists as a fallback
* Zone level lenient flag
* Validate weight makes sense for pools with a single record
* UltraDNS support for aliases and general fixes/improvements
* Misc doc fixes and improvements

## v0.9.12 - 2021-04-30 - Enough time has passed

#### Noteworthy changes

* Formal Python 2.7 support removed, deps and tooling were becoming
  unmaintainable
* octodns/octodns move, from github/octodns, more to come

#### Stuff

* ZoneFileSource supports specifying an extension & no files end in . to better
  support Windows
* LOC record type support added
* Support for pre-release versions of PowerDNS
* PowerDNS delete before create which allows A <-> CNAME etc.
* Improved validation of fqdn's in ALIAS, CNAME, etc.
* Transip support for NS records
* Support for sending plan output to a file
* DNSimple uses zone api rather than domain to support non-registered stuff,
  e.g. reverse zones.
* Support for fallback-only dynamic pools and related fixes to NS1 provider
* Initial Hetzner provider

## v0.9.11 - 2020-11-05 - We still don't know edition

#### Noteworthy changes

* ALIAS records only allowed at the root of zones - see `leient` in record docs
  for work-arounds if you really need them.

#### New Providers

* Gandi LiveDNS
* UltraDNS
* easyDNS

#### Stuff

* Add support for zones aliases
* octodns-compare: Prefix filtering and status code on on mismatch
* Implement octodns-sync --source
* Adding environment variable record injection
* Add support for wildcard SRV records, as shown in RFC 2782
* Add healthcheck option 'request_interval' for Route53 provider
* NS1 georegion, country, and catchall need to be separate groups
* Add the ability to mark a zone as lenient
* Add support for geo-targeting of CA provinces
* Update geo_data to pick up a couple renames
* Cloudflare: Add PTR Support, update rate-limit handling and pagination
* Support PowerDNS 4.3.x
* Added support for TCP health checking of dynamic records

## v0.9.10 - 2020-04-20 - Dynamic NS1 and lots of misc

* Added support for dynamic records to Ns1Provider, updated client and rate
  limiting implementation
* Moved CI to use GitHub Actions
* Set up dependabot to automatically PR requirements updates
* Pass at bumping all of the requirements and Dependabot them going forward
* Enhanced `dynamic` pool validation rules
* Delegation set support for Route53 and fix for CNAME/A ordering issues
* DNSimple sandbox support
* OVHProvider support for CAA
* Akamai rename FastDNS to EdgeDNS
* Transip bumped to 2.1.2 which should get away from its SOAP api which is EOLd

## v0.9.9 - 2019-11-04 - Python 3.7 Support

* Extensive pass through the whole codebase to support Python 3
   * Tons of updates to replace `def __cmp__` with `__eq__` and friends to
     preserve custom equality and ordering behaviors that are essential to
     octoDNS's processes.
   * Quite a few objects required the addition of `__eq__` and friends so that
     they're sortable in Python 3 now that those things are more strict. A few
     places this required jumping through hoops of sorts. Thankfully our tests
     are pretty thorough and caught a lot of issues and hopefully the whole
     plan, review, apply process will backstop that.
   * Explicit ordering of changes by (name, type) to address inconsistent
     ordering for a number of providers that just convert changes into API
     calls as they come. Python 2 sets ordered consistently, Python 3 they do
     not. https://github.com/octodns/octodns/pull/384/commits/7958233fccf9ea22d95e2fd06c48d7d0a4529e26
   * Route53 `_mod_keyer` ordering wasn't 100% complete and thus unreliable and
     random in Python 3. This has been addressed and may result in value
     reordering on next plan, no actual changes in behavior should occur.
   * `incf.countryutils` (in pypi) was last released in 2009 is not python 3
     compatible (it's country data is also pretty stale.) `pycountry_convert`
     appears to have the functionality required to replace its usage so it has
     been removed as a dependency/requirement.
   * Bunch of additional unit tests and supporting config to exercise new code
     and verify things that were run into during the Python 3 work
   * lots of `six`ing of things
* Validate Record name & fqdn length

## v0.9.8 - 2019-09-30 - One with no changes b/c PyPi description problems

* No material changes

## v0.9.7 - 2019-09-30 - It's about time

* AkamaiProvider, ConstellixProvider, MythicBeastsProvider, SelectelProvider,
  &amp; TransipPovider providers added
* Route53Provider separator fix
* YamlProvider export error around stringification
* PyPi markdown rendering fix

## v0.9.6 - 2019-07-16 - The little one that fixes stuff from the big one

* Reduced dynamic record value weight range to 0-15 so that Dyn and Route53
  match up behaviors. Dyn is limited to 0-15 and scaling that up would lose
  resolution that couldn't be recovered during populate.
* Addressed issues with Route53 change set ordering for dynamic records
* Ignore unsupported record types in DigitalOceanProvider
* Fix bugs in Route53 extra changes handling and health check managagement

## v0.9.5 - 2019-05-06 - The big one, with all the dynamic stuff

* dynamic record support, essentially a v2 version of geo records with a lot
  more flexibility and power. Also support dynamic CNAME records (alpha)
* Route53Provider dynamic record support
* DynProvider dynamic record support
* SUPPORTS_DYNAMIC is an optional property, defaults to False
* Route53Provider health checks support disabling latency measurement
* CloudflareProvider SRV record unpacking fix
* DNSMadeEasy provider uses supports to avoid blowing up on unknown record
  types
* Updates to AzureProvider lib versions
* Normalize MX/CNAME/ALIAS/PTR value to lower case
* SplitYamlProvider support added
* DynProvider fix for Traffic Directors association to records, explicit rather
  than "looks close enough"
* TinyDNS support for TXT and AAAA records and fixes to ; escaping
* pre-commit hook requires 100% code coverage

## v0.9.4 - 2019-01-28 - The one with a bunch of stuff, before the big one

* A bunch of "dynamic" stuff that'll be detailed in the next release when
  providers actually support it :grin:
* Route53Provider adds support for using session tokens
* Added support for proxying Cloudflare ALIAS records
* Dyn CAA TTL fix
* Documentation fixes and improvements
* natsort version bump to address setup issues
* DNSSimple TXT record handling fixes, ; it's always ;
* Route53Provider support for sessiom tokens
* Add ALIAS to the list of Cloudflare record types that support proxying
* Fix for TTL bug in Dyn CCA records
* Records updated so that 'octodns' record metadata is persisted through
  YamlProvider
* Added --version support to ArguementParser (thus all commands)

## v0.9.3 - 2018-10-29 - Misc. stuff sort of release

* ZoneFile source added
* Major rework/improvements to the Cloudflare record update process, fixed bugs
  and optimized it quite a bit
* Add ability to manage Cloudflare proxy flag
* Bump requests version to 2.20.0

## v0.9.2 - 2018-08-20 - More sources

* EtcHostsProvider implementation to create static/emergency best effort
  content that can be used in /etc/hosts to resolve things.
* Add lenient support to Zone.add_record, allows populate from providers that
  have allowed/created invalid data and situations where a sub-zone is being
  extracted from a parent, but the records still exist in the remote provider.
* AXFR source support added
* google-cloud-dns requirement instead of general package

## v0.9.1 - 2018-05-21 - Going backwards with setup.py

### NOTICE

Using this version on existing records with `geo` will result in
recreating all health checks. This process has been tested pretty thoroughly to
try and ensure a seamless upgrade without any traffic shifting around. It's
probably best to take extra care when updating and to try and make sure that
all health checks are passing before the first sync with `--doit`. See
[#67](https://github.com/octodns/octodns/pull/67) for more information.

* Major update to geo healthchecks to allow configuring host (header), path,
  protocol, and port [#67](https://github.com/octodns/octodns/pull/67)
* SSHFP algorithm type 4
* NS1 and DNSimple support skipping unsupported record types
* Revert back to old style setup.py &amp; requirements.txt, setup.cfg was
  causing too much pita

## v0.9.0 - 2018-03-26 - Way too long since we last met

* Way way way too much to list out here, shouldn't have waited so long
* Initial NS1 geo support
* Major reworking of `CloudflareProvider`'s update process, was only partially
  functional before, also ignore proxied records
* Fixes and improvements to better support non-ascii records and zones
* Plans indicate when Zones are going to be created
* Fix for `GoogleCloudProvider` handling of ; escapes
* Skip Alias recordsets for Route53 (unsupported concept/type)
* Make sure that Record geo values are sorted to prevent false diffs that can
  never be fixed
* `DynProvider` fix to safely roll rulesets, things could end up on rules
  without a pool and/or hitting the default rule previously.

## v0.8.8 - 2017-10-24 - Google Cloud DNS, Large TXT Record support

* Added support for "chunking" TXT records where individual values were larger
  than 255 chars. This is common with DKIM records involving multiple
  providers.
* Added `GoogleCloudProvider`
* Configurable `UnsafePlan` thresholds to allow modification of how many
  updates/deletes are allowed before a plan is declared dangerous.
* Manager.dump bug fix around empty zones.
* Prefer use of `.` over `source` in shell scripts
* `DynProvider` warns when it ignores unrecognized traffic directors.

## v0.8.7 - 2017-09-29 - OVH support

Adds an OVH provider.

## v0.8.6 - 2017-09-06 - CAA record type,

Misc fixes and improvements.

* Azure TXT record fix
* PowerDNS api support for https
* Configurable Route53 max retries and max-attempts
* Improved key ordering error message

## v0.8.5 - 2017-07-21 - Azure, NS1 escaping, & large zones

Relatively small delta this go around. No major themes or anything, just steady
progress.

* AzureProvider added thanks to work by
  [Heesu Hwang](https://github.com/h-hwang).
* Fixed some escaping issues with NS1 TXT and SPF records that were tracked down
  with the help of [Blake Stoddard](https://github.com/blakestoddard).
* Some tweaks were made to Zone.records to vastly improve handling of zones with
  very large numbers of records, no more O(N^2).

## v0.8.4 - 2017-06-28 - It's been too long

Lots of updates based on our internal use, needs, and feedback & suggestions
from our OSS users. There's too much to list out since the previous release was
cut, but I'll try to cover the highlights/important bits and promise to do
better in the future :fingers_crossed:

#### Major:

* Complete rework of record validation with lenient mode support added to
  octodns-dump so that data with validation problems can be dumped to config
  files as a starting point. octoDNS now also ignores validation errors when
  pulling the current state from a provider before planning changes. In both
  cases this is best effort.
* Naming of record keys are based on RFC-1035 and friends, previous names have
  been kept for backwards compatibility until the 1.0 release.
* Provider record type support is now explicit, i.e. opt-in, rather than
  opt-out. This prevents bugs/oversights in record handling where providers
  don't support (new) record types and didn't correctly ignore them.
* ALIAS support for DNSimple, Dyn, NS1, PowerDNS
* Ignored record support added, `octodns:\n  ignored: True`
* Ns1Provider added

#### Miscellaneous

* Use a 3rd party lib for natural sorting of keys, rather than my old
  implementation. Sorting can be disabled in the YamlProvider with
  `enforce_order: False`.
* Semi-colon/escaping fixes and improvements.
* Meta record support, `TXT octodns-meta.<zone>`. For now just
  `provider=<provider-id>`. Optionally turned on with `include_meta` manager
  config val.
* Validations check for CNAMEs co-existing with other records and error out if
  found. Was a common mistaken/unknown issue and this surfaces the problem
  early.
* Sizeable refactor in the way Route53 record translation works to make it
  cleaner/less hacky
* Lots of docs type-o fixes
* Fixed some pretty major bugs in DnsimpleProvider
* Relax UnsafePlan checks a bit, more to come here
* Set User-Agent header on Dyn health checks

## v0.8.0 - 2017-03-14 - First public release
