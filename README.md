<img src="https://raw.githubusercontent.com/octodns/octodns/main/docs/logos/octodns-logo.png?" alt="octoDNS Logo" height=251 width=404>

## DNS as code - Tools for managing DNS across multiple providers

In the vein of [infrastructure as
code](https://en.wikipedia.org/wiki/Infrastructure_as_Code) octoDNS provides a set of tools & patterns that make it easy to manage your DNS records across multiple providers. The resulting config can live in a repository and be [deployed](https://github.com/blog/1241-deploying-at-github) just like the rest of your code, maintaining a clear history and using your existing review & workflow.

The architecture is pluggable and the tooling is flexible to make it applicable to a wide variety of use-cases. Effort has been made to make adding new providers as easy as possible. In the simple case that involves writing of a single `class` and a couple hundred lines of code, most of which is translating between the provider's schema and octoDNS's. More on some of the ways we use it and how to go about extending it below and in the [/docs directory](/docs).

## Table of Contents

* [Getting started](#getting-started)
   * [Workspace](#workspace)
      * [Installing a specific commit SHA](#installing-a-specific-commit-sha)
   * [Config](#config)
      * [Dynamic Zone Config](#dynamic-zone-config)
      * [Static Zone Config](#static-zone-config)
      * [General Configuration Concepts](#general-configuration-concepts)
      * [Quick Example Record](#quick-example-record)
   * [Noop](#noop)
   * [Making changes](#making-changes)
   * [Workflow](#workflow)
   * [Bootstrapping config files](#bootstrapping-config-files)
* [Providers](#providers)
   * [Updating to use extracted providers](#updating-to-use-extracted-providers)
* [Sources](#sources)
   * [Notes](#notes)
* [Processors](#processors)
* [Automatic PTR generation](#automatic-ptr-generation)
* [Compatibility and Compliance](#compatibility-and-compliance)
   * [`lenient`](#lenient)
   * [`strict_supports`](#strict_supports)
   * [Configuring `strict_supports`](#configuring-strict_supports)
* [Custom Sources and Providers](#custom-sources-and-providers)
* [Other Uses](#other-uses)
   * [Syncing between providers](#syncing-between-providers)
   * [Dynamic sources](#dynamic-sources)
* [Contributing](#contributing)
* [Getting help](#getting-help)
* [Related Projects and Resources](#related-projects-and-resources)
* [License](#license)
* [Authors](#authors)

## Getting started

### Workspace

Running through the following commands will install the latest release of octoDNS and set up a place for your config files to live. To determine if provider specific requirements are necessary see the [providers table](#providers) below.

```console
$ mkdir dns
$ cd dns
$ python -m venv env
...
$ source env/bin/activate
# provider-specific-requirements would be things like: octodns-route53 octodns-azure
$ pip install octodns <provider-specific-requirements>
$ mkdir config
```

#### Installing a specific commit SHA

If you'd like to install a version that has not yet been released in a repeatable/safe manner you can do the following. In general octoDNS is fairly stable in between releases thanks to the plan and apply process, but care should be taken regardless.

```console
$ pip install -e git+https://git@github.com/octodns/octodns.git@<SHA>#egg=octodns
```

### Config

We start by creating a config file to tell octoDNS about our providers and the zone(s) we want it to manage. Below we're setting up a `YamlProvider` to source records from our config files and both a `Route53Provider` and `DynProvider` to serve as the targets for those records. You can have any number of zones set up and any number of sources of data and targets for records for each. You can also have multiple config files, that make use of separate accounts and each manage a distinct set of zones. A good example of this this might be `./config/staging.yaml` & `./config/production.yaml`. We'll focus on a `config/production.yaml`.

#### Dynamic Zone Config

octoDNS supports dynamically building the list of zones it will work with when source providers support it. The most common use of this would be with `YamlProvider` and a single dynamic entry to in effect use the files that exist in the provider's directory as the source of truth. Other providers may support the `list_zones` method and be available to populate zones dynamically as well. This can be especially useful when using `octodns-dump` to create an initial setup from an existing provider.

An example config would look something like:

```yaml
---
providers:
  config:
    class: octodns.provider.yaml.YamlProvider
    directory: ./config
    default_ttl: 3600
    enforce_order: True
  ns:
    class: octodns_ns1.Ns1Provider
    api_key: env/NS1_API_KEY
  route53:
    class: octodns_route53.Route53Provider
    access_key_id: env/AWS_ACCESS_KEY_ID
    secret_access_key: env/AWS_SECRET_ACCESS_KEY

zones:
  # This is a dynamic zone config. The source(s), here `config`, will be
  # queried for a list of zone names and each will dynamically be set up to
  # match the dynamic entry.
  '*':
    sources:
      - config
    targets:
      - ns1
      - route53
```

#### Static Zone Config

In cases where finer grained control is desired and the configuration of individual zones varies `zones` can be an explicit list with each configured zone listed along with its specific setup. As exemplified below `alias` zones can be useful when two zones are exact copies of each other, with the same configuration and records. YAML anchors are also helpful to avoid duplication where zones share config, but not records.

```yaml
---
manager:
  include_meta: True
  max_workers: 2

providers:
  config:
    class: octodns.provider.yaml.YamlProvider
    directory: ./config
    default_ttl: 3600
    enforce_order: True
  ns:
    class: octodns_ns1.Ns1Provider
    api_key: env/NS1_API_KEY
  route53:
    class: octodns_route53.Route53Provider
    access_key_id: env/AWS_ACCESS_KEY_ID
    secret_access_key: env/AWS_SECRET_ACCESS_KEY

zones:
  example.com.: &dual_target
    sources:
      - config
    targets:
      - ns1
      - route53

  # these have the same setup as example.com., but will have their own files
  # in the configuration directory for records.
  third.tv.: *dual_target
  fourth.tv.: *dual_target

  example.net.:
    # example.net. is an exact copy of example.com., there will not be an
    # example.net.yaml file in the config directory as `alias` includes
    # duplicating the records of the aliased zone along with its config.
    alias: example.com.

  other.com.:
    lenient: True
    sources:
      - config
    targets:
      - ns1

```

#### General Configuration Concepts

`class` is a special key that tells octoDNS what python class should be loaded. Any other keys will be passed as configuration values to that provider. In general any sensitive or frequently rotated values should come from environmental variables. When octoDNS sees a value that starts with `env/` it will look for that value in the process's environment and pass the result along.

Further information can be found in the `docstring` of each source and provider class.

The `include_meta` key in the `manager` section of the config controls the creation of a TXT record at the root of a zone that is managed by octoDNS. If set to `True`, octoDNS will create a TXT record for the root of the zone with the value `provider=<target-provider>`. If not specified, the default value for `include_meta` is `False`.

The `max_workers` key in the `manager` section of the config enables threading to parallelize the planning portion of the sync.

#### Quick Example Record

Now that we have something to tell octoDNS about our providers & zones we need to tell it about our records. We'll keep it simple for now and just create a single `A` record at the top-level of the domain.

`config/example.com.yaml`

```yaml
---
'':
  ttl: 60
  type: A
  values:
    - 1.2.3.4
    - 1.2.3.5
```

Further information can be found in [Records Documentation](/docs/records.md).

### Noop

We're ready to do a dry-run with our new setup to see what changes it would make. Since we're pretending here we'll act like there are no existing records for `example.com.` in our accounts on either provider.

```console
$ octodns-sync --config-file=./config/production.yaml
...
********************************************************************************
* example.com.
********************************************************************************
* route53 (Route53Provider)
*   Create <ARecord A 60, example.com., [u'1.2.3.4', '1.2.3.5']>
*   Summary: Creates=1, Updates=0, Deletes=0, Existing Records=0
* dyn (DynProvider)
*   Create <ARecord A 60, example.com., [u'1.2.3.4', '1.2.3.5']>
*   Summary: Creates=1, Updates=0, Deletes=0, Existing Records=0
********************************************************************************
...
```

There will be other logging information presented on the screen, but successful runs of sync will always end with a summary like the above for any providers & zones with changes. If there are no changes a message saying so will be printed instead. Above we're creating a new zone in both providers so they show the same change, but that doesn't always have to be the case. If, to start, one of them had a different state, you would see the changes octoDNS intends to make to sync them up.

### Making changes

**WARNING**: octoDNS assumes ownership of any domain you point it to. When you tell it to act it will do whatever is necessary to try and match up states including deleting any unexpected records. Be careful when playing around with octoDNS. It's best to experiment with a fake zone or one without any data that matters until you're comfortable with the system.

Now it's time to tell octoDNS to make things happen. We'll invoke it again with the same options and add a `--doit` on the end to tell it this time we actually want it to try and make the specified changes.

```console
$ octodns-sync --config-file=./config/production.yaml --doit
...
```

The output here would be the same as before with a few more log lines at the end as it makes the actual changes. After which the config in Route53 and Dyn should match what's in the yaml file.

### Workflow

In the above case we manually ran octoDNS from the command line. That works and it's better than heading into the provider GUIs and making changes by clicking around, but octoDNS is designed to be run as part of a deploy process. The implementation details are well beyond the scope of this README, but here is an example of the workflow we use at GitHub. It follows the way [GitHub itself is branch deployed](https://githubengineering.com/deploying-branches-to-github-com/).

The first step is to create a PR with your changes.

![GitHub user interface of a pull request](/docs/assets/pr.png)

Assuming the code tests and config validation statuses are green the next step is to do a noop deploy and verify that the changes octoDNS plans to make are the ones you expect.

![Output of a noop deployment command](/docs/assets/noop.png)

After that comes a set of reviews. One from a teammate who should have full context on what you're trying to accomplish and visibility into the changes you're making to do it. The other is from a member of the team here at GitHub that owns DNS, mostly as a sanity check and to make sure that best practices are being followed. As much of that as possible is baked into `octodns-validate`.

After the reviews it's time to branch deploy the change.

![Output of a deployment command](/docs/assets/deploy.png)

If that goes smoothly, you again see the expected changes, and verify them with `dig` and/or `octodns-report` you're good to hit the merge button. If there are problems you can quickly do a `.deploy dns/main` to go back to the previous state.

### Bootstrapping config files

Very few situations will involve starting with a blank slate which is why there's tooling built in to pull existing data out of providers into a matching config file.

```console
$ octodns-dump --config-file=config/production.yaml --output-dir=tmp/ example.com. route53
2017-03-15T13:33:34  INFO  Manager __init__: config_file=tmp/production.yaml
2017-03-15T13:33:34  INFO  Manager dump: zone=example.com., sources=('route53',)
2017-03-15T13:33:36  INFO  Route53Provider[route53] populate:   found 64 records
2017-03-15T13:33:36  INFO  YamlProvider[dump] plan: desired=example.com.
2017-03-15T13:33:36  INFO  YamlProvider[dump] plan:   Creates=64, Updates=0, Deletes=0, Existing Records=0
2017-03-15T13:33:36  INFO  YamlProvider[dump] apply: making changes
```

The above command pulled the existing data out of Route53 and placed the results into `tmp/example.com.yaml`. That file can be inspected and moved into `config/` to become the new source. If things are working as designed a subsequent noop sync should show zero changes.

Note that a [Dynamic Zone Config](#dynamic-zone-config) and be really powerful in combination with `octodns-dump` allowing you to quickly create a set of octoDNS zone files for all the zones configured in your sources.

```console
$ octodns-dump --config-file=config/production.yaml --output-dir=tmp/ '*' route53
...
```

It is important to review any `WARNING` log lines printed out during an `octodns-dump` invocation as it will give you information about records that aren't supported fully or at all by octoDNS and thus won't be exact matches or included in the dumps. Generally records that cannot be converted are either of a type that octoDNS does not support or those that include "dynamic" functionality that doesn't match octoDNS's behaviors.

## Providers

The table below lists the providers octoDNS supports. They are maintained in their own repositories and released as independent modules.

| Provider | Module | Notes |
|--|--|--|
| [Akamai Edge DNS](https://www.akamai.com/products/edge-dns) | [octodns_edgedns](https://github.com/octodns/octodns-edgedns/) | |
| [Amazon Route 53](https://aws.amazon.com/route53/) | [octodns_route53](https://github.com/octodns/octodns-route53) | |
| [Azure DNS](https://azure.microsoft.com/en-us/services/dns/) | [octodns_azure](https://github.com/octodns/octodns-azure/) | |
| [BIND, AXFR, RFC-2136](https://www.isc.org/bind/) | [octodns_bind](https://github.com/octodns/octodns-bind/) | |
| [Cloudflare DNS](https://www.cloudflare.com/dns/) | [octodns_cloudflare](https://github.com/octodns/octodns-cloudflare/) | |
| [Constellix](https://constellix.com/) | [octodns_constellix](https://github.com/octodns/octodns-constellix/) | |
| [DigitalOcean](https://docs.digitalocean.com/products/networking/dns/) | [octodns_digitalocean](https://github.com/octodns/octodns-digitalocean/) | |
| [DNS Made Easy](https://dnsmadeeasy.com/) | [octodns_dnsmadeeasy](https://github.com/octodns/octodns-dnsmadeeasy/) | |
| [DNSimple](https://dnsimple.com/) | [octodns_dnsimple](https://github.com/octodns/octodns-dnsimple/) | |
| [Dyn](https://www.oracle.com/cloud/networking/dns/) ([deprecated](https://www.oracle.com/corporate/acquisitions/dyn/technologies/migrate-your-services/)) | [octodns_dyn](https://github.com/octodns/octodns-dyn/) | |
| [easyDNS](https://easydns.com/) | [octodns_easydns](https://github.com/octodns/octodns-easydns/) | |
| [EdgeCenter DNS](https://edgecenter.ru/dns/) | [octodns_edgecenter](https://github.com/octodns/octodns-edgecenter/) | |
| /etc/hosts | [octodns_etchosts](https://github.com/octodns/octodns-etchosts/) | |
| [Gandi](https://www.gandi.net/en-US/domain/dns) | [octodns_gandi](https://github.com/octodns/octodns-gandi/) | |
| [G-Core Labs DNS](https://gcorelabs.com/dns/) | [octodns_gcore](https://github.com/octodns/octodns-gcore/) | |
| [Google Cloud DNS](https://cloud.google.com/dns) | [octodns_googlecloud](https://github.com/octodns/octodns-googlecloud/) | |
| [Hetzner DNS](https://www.hetzner.com/dns-console) | [octodns_hetzner](https://github.com/octodns/octodns-hetzner/) | |
| [Mythic Beasts DNS](https://www.mythic-beasts.com/support/hosting/dns) | [octodns_mythicbeasts](https://github.com/octodns/octodns-mythicbeasts/) | |
| [NS1](https://ns1.com/products/managed-dns) | [octodns_ns1](https://github.com/octodns/octodns-ns1/) | |
| [OVHcloud DNS](https://www.ovhcloud.com/en/domains/dns-subdomain/) | [octodns_ovh](https://github.com/octodns/octodns-ovh/) | |
| [PowerDNS](https://www.powerdns.com/) | [octodns_powerdns](https://github.com/octodns/octodns-powerdns/) | |
| [Rackspace](https://www.rackspace.com/library/what-is-dns) | [octodns_rackspace](https://github.com/octodns/octodns-rackspace/) | |
| [Scaleway](https://www.scaleway.com/en/dns/) | [octodns_scaleway](https://github.com/scaleway/octodns-scaleway) | |
| [Selectel](https://selectel.ru/en/services/additional/dns/) | [octodns_selectel](https://github.com/octodns/octodns-selectel/) | |
| [SPF Value Management](https://github.com/octodns/octodns-spf) | [octodns_spf](https://github.com/octodns/octodns-spf/) | |
| [TransIP](https://www.transip.eu/knowledgebase/entry/155-dns-and-nameservers/) | [octodns_transip](https://github.com/octodns/octodns-transip/) | |
| [UltraDNS](https://vercara.com/authoritative-dns) | [octodns_ultra](https://github.com/octodns/octodns-ultra/) | |
| [YamlProvider](/octodns/provider/yaml.py) | built-in | Supports all record types and core functionality |

### Updating to use extracted providers

1. Include the extracted module in your python environment, e.g. if using Route53 that would require adding the `octodns_route53` module to your requirements.txt, setup.py, or similar.
1. Update the `class` value for your provider to the new path, e.g. again for Route53 that would be replacing `octodns.provider.route53.Route53Provider` with `octodns_route53.Route53Provider`

The module required and provider class path for extracted providers can be found in the table above.

## Sources

Similar to providers, but can only serve to populate records into a zone, cannot be synced to.

| Source | Record Support | Dynamic | Notes |
|--|--|--|--|
| [EnvVarSource](/octodns/source/envvar.py) | TXT | No | read-only environment variable injection |
| [AxfrSource](https://github.com/octodns/octodns-bind/) | A, AAAA, CAA, CNAME, LOC, MX, NS, PTR, SPF, SRV, TXT | No | read-only |
| [ZoneFileSource](https://github.com/octodns/octodns-bind/) | A, AAAA, CAA, CNAME, MX, NS, PTR, SPF, SRV, TXT | No | read-only |
| [TinyDnsFileSource](/octodns/source/tinydns.py) | A, CNAME, MX, NS, PTR | No | read-only |

### Notes

* ALIAS support varies a lot from provider to provider care should be taken to verify that your needs are met in detail.
   * Dyn's UI doesn't allow editing or view of TTL, but the API accepts and stores the value provided, this value does not appear to be used when served
   * Dnsimple's uses the configured TTL when serving things through the ALIAS, there's also a secondary TXT record created alongside the ALIAS that octoDNS ignores
* octoDNS itself supports non-ASCII character sets, but in testing Cloudflare is the only provider where that is currently functional end-to-end. Others have failures either in the client libraries or API calls

## Processors

| Processor | Description |
|--|--|
| [AcmeMangingProcessor](/octodns/processor/acme.py) | Useful when processes external to octoDNS are managing acme challenge DNS records, e.g. LetsEncrypt |
| [AutoArpa](/octodns/processor/arpa.py) | See [Automatic PTR generation](#automatic-ptr-generation) below |
| [EnsureTrailingDots](/octodns/processor/trailing_dots.py) | Processor that ensures ALIAS, CNAME, DNAME, MX, NS, PTR, and SRVs have trailing dots |
| [ExcludeRootNsChanges](/octodns/processor/filter.py) | Filter that errors or warns on planned root/APEX NS records changes. |
| [IgnoreRootNsFilter](/octodns/processor/filter.py) | Filter that IGNORES root/APEX NS records and prevents octoDNS from trying to manage them (where supported.) |
| [MetaProcessor](/octodns/processor/meta.py) | Adds a special meta record with timing, UUID, providers, and/or version to aid in debugging and monitoring. |
| [NameAllowlistFilter](/octodns/processor/filter.py) | Filter that ONLY manages records that match specified naming patterns, all others will be ignored |
| [NameRejectlistFilter](/octodns/processor/filter.py) | Filter that IGNORES records that match specified naming patterns, all others will be managed |
| [ValueAllowlistFilter](/octodns/processor/filter.py) | Filter that ONLY manages records that match specified value patterns based on `rdata_text`, all others will be ignored |
| [ValueRejectlistFilter](/octodns/processor/filter.py) | Filter that IGNORES records that match specified value patterns based on `rdata_text`, all others will be managed |
| [OwnershipProcessor](/octodns/processor/ownership.py) | Processor that implements ownership in octoDNS so that it can manage only the records in a zone in sources and will ignore all others. |
| [SpfDnsLookupProcessor](/octodns/processor/spf.py) | Processor that checks SPF values for violations of DNS query limits |
| [TtlRestrictionFilter](/octodns/processor/restrict.py) | Processor that restricts the allow TTL values to a specified range or list of specific values |
| [TypeAllowlistFilter](/octodns/processor/filter.py) | Filter that ONLY manages records of specified types, all others will be ignored |
| [TypeRejectlistFilter](/octodns/processor/filter.py) | Filter that IGNORES records of specified types, all others will be managed |
| [octodns-spf](https://github.com/octodns/octodns-spf) | SPF Value Management for octoDNS |

## Automatic PTR generation

octoDNS supports automatically generating PTR records from the `A`/`AAAA` records it manages. For more information see the [auto-arpa documentation](/docs/auto_arpa.md).

## Compatibility and Compliance

### `lenient`

`lenient` mostly focuses on the details of `Record`s and standards compliance. When set to `true` octoDNS will allow non-compliant configurations & values where possible. For example CNAME values that don't end with a `.`, label length restrictions, and invalid geo codes on `dynamic` records. When in lenient mode octoDNS will log validation problems at `WARNING` and try and continue with the configuration or source data as it exists. See [Lenience](/docs/records.md#lenience) for more information on the concept and how it can be configured.

### `strict_supports`

`strict_supports` is a `Provider` level parameter that comes into play when a provider has been asked to create a record that it is unable to support. The simplest case of this would be record type, e.g. `SSHFP` not being supported by `AzureProvider`. If such a record is passed to an `AzureProvider` as a target the provider will take action based on the `strict_supports`. When `true` it will throw an exception saying that it's unable to create the record, when set to `false` it will log at `WARNING` with information about what it's unable to do and how it is attempting to work around it. Other examples of things that cannot be supported would be `dynamic` records on a provider that only supports simple or the lack of support for specific geos in a provider, e.g. Route53Provider does not support `NA-CA-*`.

It is worth noting that these errors will happen during the plan phase of things so that problems will be visible without having to make changes.

This concept is currently a work in progress and only partially implemented. While work is on-going `strict_supports` will default to `false`. Once the work is considered complete & ready the default will change to `true` as it's a much safer and less surprising default as what you configure is what you'll get unless an error is thrown telling you why it cannot be done. You will then have the choice to explicitly request that things continue with work-arounds with `strict_supports` set to `false`. In the meantime it is encouraged that you manually configure the parameter to `true` in your provider configs.

### Configuring `strict_supports`

The `strict_supports` parameter is available on all providers and can be configured in YAML as follows:

```yaml
providers:
  someprovider:
    class: whatever.TheProvider
    ...
    strict_supports: true
```

## Custom Sources and Providers

You can check out the [source](/octodns/source/) and [provider](/octodns/provider/) directory to see what's currently supported. Sources act as a source of record information. AxfrSource and TinyDnsFileSource are currently the only OSS sources, though we have several others internally that are specific to our environment. These include something to pull host data from  [gPanel](https://githubengineering.com/githubs-metal-cloud/) and a similar provider that sources information about our network gear to create both `A` & `PTR` records for their interfaces. Things that might make good OSS sources might include an `ElbSource` that pulls information about [AWS Elastic Load Balancers](https://aws.amazon.com/elasticloadbalancing/) and dynamically creates `CNAME`s for them, or `Ec2Source` that pulls instance information so that records can be created for hosts similar to how our `GPanelProvider` works.

Most of the things included in octoDNS are providers, the obvious difference being that they can serve as both sources and targets of data. We'd really like to see this list grow over time so if you use an unsupported provider then PRs are welcome. The existing providers should serve as reasonable examples. Those that have no GeoDNS support are relatively straightforward. Unfortunately most of the APIs involved to do GeoDNS style traffic management are complex and somewhat inconsistent so adding support for that function would be nice, but is optional and best done in a separate pass.

The `class` key in the providers config section can be used to point to arbitrary classes in the python path so internal or 3rd party providers can easily be included with no coordination beyond getting them into PYTHONPATH, most likely installed into the virtualenv with octoDNS.

For examples of building third-party sources and providers, see [Related Projects & Resources](#related-projects-and-resources).

## Other Uses

### Syncing between providers

While the primary use-case is to sync a set of yaml config files up to one or more DNS providers, octoDNS has been built in such a way that you can easily source and target things arbitrarily. As a quick example the config below would sync `githubtest.net.` from Route53 to Dyn.

```yaml
---
providers:
  route53:
    class: octodns.provider.route53.Route53Provider
    access_key_id: env/AWS_ACCESS_KEY_ID
    secret_access_key: env/AWS_SECRET_ACCESS_KEY
  dyn:
    class: octodns.provider.dyn.DynProvider
    customer: env/DYN_CUSTOMER
    username: env/DYN_USERNAME
    password: env/DYN_PASSWORD

zones:

  githubtest.net.:
    sources:
      - route53
    targets:
      - dyn
```

### Dynamic sources

Internally we use custom sources to create records based on dynamic data that changes frequently without direct human intervention. An example of that might look something like the following. For hosts this mechanism is janitorial, run periodically, making sure the correct records exist as long as the host is alive and ensuring they are removed after the host is destroyed. The host provisioning and destruction processes do the actual work to create and destroy the records.

```yaml
---
providers:
  gpanel-site:
    class: github.octodns.source.gpanel.GPanelProvider
    host: 'gpanel.site.github.foo'
    token: env/GPANEL_SITE_TOKEN
  powerdns-site:
    class: octodns.provider.powerdns.PowerDnsProvider
    host: 'internal-dns.site.github.foo'
    api_key: env/POWERDNS_SITE_API_KEY

zones:

  hosts.site.github.foo.:
    sources:
      - gpanel-site
    targets:
      - powerdns-site
```

## Contributing

Please see our [contributing document](/CONTRIBUTING.md) if you would like to participate!

## Getting help

If you have a problem or suggestion, please [open an issue](https://github.com/octodns/octodns/issues/new) in this repository, and we will do our best to help. Please note that this project adheres to the [Contributor Covenant Code of Conduct](/CODE_OF_CONDUCT.md).

## Related Projects and Resources

- **GitHub Action:** [octoDNS-Sync](https://github.com/marketplace/actions/octodns-sync)
- **NixOS Integration:** [NixOS-DNS](https://github.com/Janik-Haag/nixos-dns/)
- **Sample Implementations.** See how others are using it
  - [`hackclub/dns`](https://github.com/hackclub/dns)
  - [`kubernetes/k8s.io:/dns`](https://github.com/kubernetes/k8s.io/tree/main/dns)
  - [`g0v-network/domains`](https://github.com/g0v-network/domains)
  - [`jekyll/dns`](https://github.com/jekyll/dns)
- **Custom Sources & Providers.**
  - [`octodns/octodns-ddns`](https://github.com/octodns/octodns-ddns): A simple Dynamic DNS source.
  - [`doddo/octodns-lexicon`](https://github.com/doddo/octodns-lexicon): Use [Lexicon](https://github.com/AnalogJ/lexicon) providers as octoDNS providers.
  - [`asyncon/octoblox`](https://github.com/asyncon/octoblox): [Infoblox](https://www.infoblox.com/) provider.
  - [`sukiyaki/octodns-netbox`](https://github.com/sukiyaki/octodns-netbox): [NetBox](https://github.com/netbox-community/netbox) source.
  - [`jcollie/octodns-netbox-dns`](https://github.com/jcollie/octodns-netbox-dns): [NetBox-DNS Plugin](https://github.com/auroraresearchlab/netbox-dns) provider.
  - [`kompetenzbolzen/octodns-custom-provider`](https://github.com/kompetenzbolzen/octodns-custom-provider): zonefile provider & phpIPAM source.
  - [`Financial-Times/octodns-fastly`](https://github.com/Financial-Times/octodns-fastly): An octoDNS source for Fastly.
- **Resources.**
  - Article: [Visualising DNS records with Neo4j](https://medium.com/@costask/querying-and-visualising-octodns-records-with-neo4j-f4f72ab2d474) + code
  - Video: [FOSDEM 2019 - DNS as code with octodns](https://archive.fosdem.org/2019/schedule/event/dns_octodns/)
  - GitHub Blog: [Enabling DNS split authority with octoDNS](https://github.blog/2017-04-27-enabling-split-authority-dns-with-octodns/)
  - Tutorial: [How To Deploy and Manage Your DNS using octoDNS on Ubuntu 18.04](https://www.digitalocean.com/community/tutorials/how-to-deploy-and-manage-your-dns-using-octodns-on-ubuntu-18-04)
  - Cloudflare Blog: [Improving the Resiliency of Our Infrastructure DNS Zone](https://blog.cloudflare.com/improving-the-resiliency-of-our-infrastructure-dns-zone/)

If you know of any other resources, please do let us know!

## License

octoDNS is licensed under the [MIT license](LICENSE).

The MIT license grant is not for GitHub's trademarks, which include the logo designs. GitHub reserves all trademark and copyright rights in and to all GitHub trademarks. GitHub's logos include, for instance, the stylized designs that include "logo" in the file title in the following folder: https://github.com/octodns/octodns/tree/main/docs/logos/

GitHub® and its stylized versions and the Invertocat mark are GitHub's Trademarks or registered Trademarks. When using GitHub's logos, be sure to follow the GitHub logo guidelines.

## Authors

octoDNS was designed and authored by [Ross McFarland](https://github.com/ross) and [Joe Williams](https://github.com/joewilliams). See https://github.com/octodns/octodns/graphs/contributors for a complete list of people who've contributed.
