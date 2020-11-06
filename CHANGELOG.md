## v0.9.11 - 2020-11-05 - We still don't know edition

#### Noteworthy changtes

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
     not. https://github.com/github/octodns/pull/384/commits/7958233fccf9ea22d95e2fd06c48d7d0a4529e26
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
* Route53Provider seperator fix
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
try and ensure a seemless upgrade without any traffic shifting around. It's
probably best to take extra care when updating and to try and make sure that
all health checks are passing before the first sync with `--doit`. See
[#67](https://github.com/github/octodns/pull/67) for more information.

* Major update to geo healthchecks to allow configuring host (header), path,
  protocol, and port [#67](https://github.com/github/octodns/pull/67)
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
