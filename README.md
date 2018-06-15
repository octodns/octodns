<img src="/docs/logos/octodns-logo.png?" height=251 width=404>

## DNS as code - Tools for managing DNS across multiple providers

In the vein of [infrastructure as
code](https://en.wikipedia.org/wiki/Infrastructure_as_Code) OctoDNS provides a set of tools & patterns that make it easy to manage your DNS records across multiple providers. The resulting config can live in a repository and be [deployed](https://github.com/blog/1241-deploying-at-github) just like the rest of your code, maintaining a clear history and using your existing review & workflow.

The architecture is pluggable and the tooling is flexible to make it applicable to a wide variety of use-cases. Effort has been made to make adding new providers as easy as possible. In the simple case that involves writing of a single `class` and a couple hundred lines of code, most of which is translating between the provider's schema and OctoDNS's. More on some of the ways we use it and how to go about extending it below and in the [/docs directory](/docs).

It is similar to [Netflix/denominator](https://github.com/Netflix/denominator).

## Getting started

### Workspace

Running through the following commands will install the latest release of OctoDNS and set up a place for your config files to live. To determine if provider specific requirements are necessary see the [Supported providers table](#supported-providers) below.

```
$ mkdir dns
$ cd dns
$ virtualenv env
...
$ source env/bin/activate
$ pip install octodns <provider-specific-requirements>
$ mkdir config
```

### Config

We start by creating a config file to tell OctoDNS about our providers and the zone(s) we want it to manage. Below we're setting up a `YamlProvider` to source records from our config files and both a `Route53Provider` and `DynProvider` to serve as the targets for those records. You can have any number of zones set up and any number of sources of data and targets for records for each. You can also have multiple config files, that make use of separate accounts and each manage a distinct set of zones. A good example of this this might be `./config/staging.yaml` & `./config/production.yaml`. We'll focus on a `config/production.yaml`.

```yaml
---
providers:
  config:
    class: octodns.provider.yaml.YamlProvider
    directory: ./config
  dyn:
    class: octodns.provider.dyn.DynProvider
    customer: 1234
    username: 'username'
    password: env/DYN_PASSWORD
  route53:
    class: octodns.provider.route53.Route53Provider
    access_key_id: env/AWS_ACCESS_KEY_ID
    secret_access_key: env/AWS_SECRET_ACCESS_KEY

zones:
  example.com.:
    sources:
      - config
    targets:
      - dyn
      - route53
```

`class` is a special key that tells OctoDNS what python class should be loaded. Any other keys will be passed as configuration values to that provider. In general any sensitive or frequently rotated values should come from environmental variables. When OctoDNS sees a value that starts with `env/` it will look for that value in the process's environment and pass the result along.

Further information can be found in the `docstring` of each source and provider class.

Now that we have something to tell OctoDNS about our providers & zones we need to tell it about or records. We'll keep it simple for now and just create a single `A` record at the top-level of the domain.

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

```
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

There will be other logging information presented on the screen, but successful runs of sync will always end with a summary like the above for any providers & zones with changes. If there are no changes a message saying so will be printed instead. Above we're creating a new zone in both providers so they show the same change, but that doesn't always have to be the case. If to start one of them had a different state you would see the changes OctoDNS intends to make to sync them up.

### Making changes

**WARNING**: OctoDNS assumes ownership of any domain you point it to. When you tell it to act it will do whatever is necessary to try and match up states including deleting any unexpected records. Be careful when playing around with OctoDNS. It's best to experiment with a fake zone or one without any data that matters until you're comfortable with the system.

Now it's time to tell OctoDNS to make things happen. We'll invoke it again with the same options and add a `--doit` on the end to tell it this time we actually want it to try and make the specified changes.

```
$ octodns-sync --config-file=./config/production.yaml --doit
...
```

The output here would be the same as before with a few more log lines at the end as it makes the actual changes. After which the config in Route53 and Dyn should match what's in the yaml file.

### Workflow

In the above case we manually ran OctoDNS from the command line. That works and it's better than heading into the provider GUIs and making changes by clicking around, but OctoDNS is designed to be run as part of a deploy process. The implementation details are well beyond the scope of this README, but here is an example of the workflow we use at GitHub. It follows the way [GitHub itself is branch deployed](https://githubengineering.com/deploying-branches-to-github-com/).

The first step is to create a PR with your changes.

![](/docs/assets/pr.png)

Assuming the code tests and config validation statuses are green the next step is to do a noop deploy and verify that the changes OctoDNS plans to make are the ones you expect.

![](/docs/assets/noop.png)

After that comes a set of reviews. One from a teammate who should have full context on what you're trying to accomplish and visibility in to the changes you're making to do it. The other is from a member of the team here at GitHub that owns DNS, mostly as a sanity check and to make sure that best practices are being followed. As much of that as possible is baked into `octodns-validate`.

After the reviews it's time to branch deploy the change.

![](/docs/assets/deploy.png)

If that goes smoothly, you again see the expected changes, and verify them with `dig` and/or `octodns-report` you're good to hit the merge button. If there are problems you can quickly do a `.deploy dns/master` to go back to the previous state.

### Bootstrapping config files

Very few situations will involve starting with a blank slate which is why there's tooling built in to pull existing data out of providers into a matching config file.

```
$ octodns-dump --config-file=config/production.yaml --output-dir=tmp/ example.com. route53
2017-03-15T13:33:34  INFO  Manager __init__: config_file=tmp/production.yaml
2017-03-15T13:33:34  INFO  Manager dump: zone=example.com., sources=('route53',)
2017-03-15T13:33:36  INFO  Route53Provider[route53] populate:   found 64 records
2017-03-15T13:33:36  INFO  YamlProvider[dump] plan: desired=example.com.
2017-03-15T13:33:36  INFO  YamlProvider[dump] plan:   Creates=64, Updates=0, Deletes=0, Existing Records=0
2017-03-15T13:33:36  INFO  YamlProvider[dump] apply: making changes
```

The above command pulled the existing data out of Route53 and placed the results into `tmp/example.com.yaml`. That file can be inspected and moved into `config/` to become the new source. If things are working as designed a subsequent noop sync should show zero changes.

## Supported providers

| Provider | Requirements | Record Support | GeoDNS Support | Notes |
|--|--|--|--|--|
| [AzureProvider](/octodns/provider/azuredns.py) | azure-mgmt-dns | A, AAAA, CNAME, MX, NS, PTR, SRV, TXT | No | |
| [CloudflareProvider](/octodns/provider/cloudflare.py) | | A, AAAA, ALIAS, CAA, CNAME, MX, NS, SPF, SRV, TXT | No | CAA tags restricted |
| [DigitalOceanProvider](/octodns/provider/digitalocean.py) | | A, AAAA, CAA, CNAME, MX, NS, TXT, SRV | No | CAA tags restricted |
| [DnsMadeEasyProvider](/octodns/provider/dnsmadeeasy.py) | | A, AAAA, CAA, CNAME, MX, NS, PTR, SPF, SRV, TXT | No | CAA tags restricted |
| [DnsimpleProvider](/octodns/provider/dnsimple.py) | | All | No | CAA tags restricted |
| [DynProvider](/octodns/provider/dyn.py) | dyn | All | Yes | |
| [GoogleCloudProvider](/octodns/provider/googlecloud.py) | google-cloud | A, AAAA, CAA, CNAME, MX, NAPTR, NS, PTR, SPF, SRV, TXT  | No | |
| [Ns1Provider](/octodns/provider/ns1.py) | nsone | All | Yes | No health checking for GeoDNS |
| [OVH](/octodns/provider/ovh.py) | ovh | A, AAAA, CNAME, MX, NAPTR, NS, PTR, SPF, SRV, SSHFP, TXT, DKIM | No | |
| [PowerDnsProvider](/octodns/provider/powerdns.py) | | All | No | |
| [Rackspace](/octodns/provider/rackspace.py) | | A, AAAA, ALIAS, CNAME, MX, NS, PTR, SPF, TXT | No |  |
| [Route53](/octodns/provider/route53.py) | boto3 | A, AAAA, CAA, CNAME, MX, NAPTR, NS, PTR, SPF, SRV, TXT | Yes | |
| [TinyDNSSource](/octodns/source/tinydns.py) | | A, CNAME, MX, NS, PTR | No | read-only |
| [YamlProvider](/octodns/provider/yaml.py) | | All | Yes | config |

#### Notes

* ALIAS support varies a lot from provider to provider care should be taken to verify that your needs are met in detail.
   * Dyn's UI doesn't allow editing or view of TTL, but the API accepts and stores the value provided, this value does not appear to be used when served
   * Dnsimple's uses the configured TTL when serving things through the ALIAS, there's also a secondary TXT record created alongside the ALIAS that octoDNS ignores
* octoDNS itself supports non-ASCII character sets, but in testing Cloudflare is the only provider where that is currently functional end-to-end. Others have failures either in the client libraries or API calls

## Custom Sources and Providers

You can check out the [source](/octodns/source/) and [provider](/octodns/provider/) directory to see what's currently supported. Sources act as a source of record information. TinyDnsProvider is currently the only OSS source, though we have several others internally that are specific to our environment. These include something to pull host data from  [gPanel](https://githubengineering.com/githubs-metal-cloud/) and a similar provider that sources information about our network gear to create both `A` & `PTR` records for their interfaces. Things that might make good OSS sources might include an `ElbSource` that pulls information about [AWS Elastic Load Balancers](https://aws.amazon.com/elasticloadbalancing/) and dynamically creates `CNAME`s for them, or `Ec2Source` that pulls instance information so that records can be created for hosts similar to how our `GPanelProvider` works. An `AxfrSource` could be really interesting as well. Another case where a source may make sense is if you'd like to export data from a legacy service that you have no plans to push changes back into.

Most of the things included in OctoDNS are providers, the obvious difference being that they can serve as both sources and targets of data. We'd really like to see this list grow over time so if you use an unsupported provider then PRs are welcome. The existing providers should serve as reasonable examples. Those that have no GeoDNS support are relatively straightforward. Unfortunately most of the APIs involved to do GeoDNS style traffic management are complex and somewhat inconsistent so adding support for that function would be nice, but is optional and best done in a separate pass.

The `class` key in the providers config section can be used to point to arbitrary classes in the python path so internal or 3rd party providers can easily be included with no coordination beyond getting them into PYTHONPATH, most likely installed into the virtualenv with OctoDNS.

## Other Uses

### Syncing between providers

While the primary use-case is to sync a set of yaml config files up to one or more DNS providers, OctoDNS has been built in such a way that you can easily source and target things arbitrarily. As a quick example the config below would sync `githubtest.net.` from Route53 to Dyn.

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

If you have a problem or suggestion, please [open an issue](https://github.com/github/octodns/issues/new) in this repository, and we will do our best to help. Please note that this project adheres to the [Contributor Covenant Code of Conduct](/CODE_OF_CONDUCT.md).

## License

OctoDNS is licensed under the [MIT license](LICENSE).

The MIT license grant is not for GitHub's trademarks, which include the logo designs. GitHub reserves all trademark and copyright rights in and to all GitHub trademarks. GitHub's logos include, for instance, the stylized designs that include "logo" in the file title in the following folder: https://github.com/github/octodns/tree/master/docs/logos/

GitHub® and its stylized versions and the Invertocat mark are GitHub's Trademarks or registered Trademarks. When using GitHub's logos, be sure to follow the GitHub logo guidelines.

## Authors

OctoDNS was designed and authored by [Ross McFarland](https://github.com/ross) and [Joe Williams](https://github.com/joewilliams). It is now maintained, reviewed, and tested by Ross, Joe, and the rest of the Site Reliability Engineering team at GitHub.
