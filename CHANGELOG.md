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

* Use a 3rd party lib for nautrual sorting of keys, rather than my old
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
