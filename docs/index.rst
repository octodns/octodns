.. image:: assets/octodns-logo.png
   :alt: GitHub user interface of a pull request

DNS as Code
===========

Tools for managing DNS across multiple providers
------------------------------------------------

In the vein of infrastructure as code octoDNS provides a set of tools &
patterns that make it easy to manage your DNS records across multiple
providers. The resulting config can live in a repository and be deployed just
like the rest of your code, maintaining a clear history and using your existing
review & workflow.

The architecture is pluggable and the tooling is flexible to make it applicable
to a wide variety of use-cases. Effort has been made to make adding new
providers as easy as possible. In the simple case that involves writing of a
single class and a couple hundred lines of code, most of which is translating
between the provider's schema and octoDNS's.

Documentation
-------------

.. toctree::
   :maxdepth: 1

   getting-started.rst
   records.md
   configuration.rst
   dynamic_records.rst
   auto_arpa.rst
   examples/README.rst
   api.rst
   changelog.md

.. _provider-list:

Providers
---------

The table below lists the providers octoDNS supports. They are maintained in
their own repositories and released as independent modules.

.. list-table::
   :header-rows: 1

   * - Provider
     - Module
     - Notes
   * - /etc/hosts
     - `octodns_etchosts`_
     -
   * - `Akamai Edge DNS`_
     - `octodns_edgedns`_
     -
   * - `Amazon Route 53`_
     - `octodns_route53`_
     -
   * - `AutoDNS`_
     - `octodns_autodns`_
     -
   * - `Azion DNS`_
     - `octodns_azion`_
     -
   * - `Azure DNS`_
     - `octodns_azure`_
     -
   * - `BIND, AXFR, RFC-2136`_
     - `octodns_bind`_
     -
   * - `Bunny DNS`_
     - `octodns_bunny`_
     -
   * - `Cloudflare DNS`_
     - `octodns_cloudflare`_
     -
   * - `ClouDNS`_
     - `octodns_cloudns`_
     -
   * - `Constellix`_
     - `octodns_constellix`_
     -
   * - `deSEC`_
     - `octodns_desec`_
     -
   * - `DigitalOcean`_
     - `octodns_digitalocean`_
     -
   * - `DNS Made Easy`_
     - `octodns_dnsmadeeasy`_
     -
   * - `DNSimple`_
     - `octodns_dnsimple`_
     -
   * - `Dyn`_ [deprecated]
     - `octodns_dyn`_
     -
   * - `easyDNS`_
     - `octodns_easydns`_
     -
   * - `EdgeCenter DNS`_
     - `octodns_edgecenter`_
     -
   * - `Fastly`_
     - `Financial-Times/octodns-fastly`_
     -
   * - `G-Core Labs DNS`_
     - `octodns_gcore`_
     -
   * - `Gandi`_
     - `octodns_gandi`_
     -
   * - `Google Cloud DNS`_
     - `octodns_googlecloud`_
     -
   * - `Hetzner DNS`_
     - `octodns_hetzner`_
     -
   * - `Infoblox`_
     - `asyncon/octoblox`_
     -
   * - `Infomaniak`_
     - `octodns_infomaniak`_
     -
   * - `Lexicon`_
     - `dns-lexicon/dns-lexicon`_
     -
   * - `Mythic Beasts DNS`_
     - `octodns_mythicbeasts`_
     -
   * - `NetBox-DNS Plugin`_
     - `olofvndrhr/octodns-netbox-dns`_
     -
   * - `NS1`_
     - `octodns_ns1`_
     -
   * - `OVHcloud DNS`_
     - `octodns_ovh`_
     -
   * - `Pi-hole`_
     - `jvoss/octodns-pihole`_
     -
   * - `PowerDNS`_
     - `octodns_powerdns`_
     -
   * - `Rackspace`_
     - `octodns_rackspace`_
     -
   * - `Scaleway`_
     - `octodns_scaleway`_
     -
   * - `Selectel`_
     - `octodns_selectel`_
     -
   * - `SPF Value Management`_
     - `octodns_spf`_
     -
   * - `TransIP`_
     - `octodns_transip`_
     -
   * - `UltraDNS`_
     - `octodns_ultra`_
     -
   * - `YamlProvider`_
     - built-in
     - Supports all record types and core functionality
   * - Zonefile
     - `kompetenzbolzen/octodns-custom-provider`_
     -

.. _octodns_etchosts: https://github.com/octodns/octodns-etchosts/
.. _Akamai Edge DNS: https://www.akamai.com/products/edge-dns
.. _octodns_edgedns: https://github.com/octodns/octodns-edgedns/
.. _Amazon Route 53: https://aws.amazon.com/route53/
.. _octodns_route53: https://github.com/octodns/octodns-route53
.. _AutoDNS: https://www.internetx.com/autodns/
.. _octodns_autodns: https://github.com/octodns/octodns-autodns
.. _Azion DNS: https://www.azion.com/en/products/edge-dns/
.. _octodns_azion: https://github.com/aziontech/octodns-azion/
.. _Azure DNS: https://azure.microsoft.com/en-us/services/dns/
.. _octodns_azure: https://github.com/octodns/octodns-azure/
.. _BIND, AXFR, RFC-2136: https://www.isc.org/bind/
.. _octodns_bind: https://github.com/octodns/octodns-bind/
.. _Bunny DNS: https://bunny.net/dns/
.. _octodns_bunny: https://github.com/Relkian/octodns-bunny
.. _Cloudflare DNS: https://www.cloudflare.com/dns/
.. _octodns_cloudflare: https://github.com/octodns/octodns-cloudflare/
.. _ClouDNS: https://www.cloudns.net/
.. _octodns_cloudns: https://github.com/ClouDNS/octodns_cloudns
.. _Constellix: https://constellix.com/
.. _octodns_constellix: https://github.com/octodns/octodns-constellix/
.. _deSEC: https://desec.io/
.. _octodns_desec: https://github.com/rootshell-labs/octodns-desec
.. _DigitalOcean: https://docs.digitalocean.com/products/networking/dns/
.. _octodns_digitalocean: https://github.com/octodns/octodns-digitalocean/
.. _DNS Made Easy: https://dnsmadeeasy.com/
.. _octodns_dnsmadeeasy: https://github.com/octodns/octodns-dnsmadeeasy/
.. _DNSimple: https://dnsimple.com/
.. _octodns_dnsimple: https://github.com/octodns/octodns-dnsimple/
.. _Dyn:  https://www.oracle.com/cloud/networking/dns/
.. _octodns_dyn: https://github.com/octodns/octodns-dyn/
.. _easyDNS: https://easydns.com/
.. _octodns_easydns: https://github.com/octodns/octodns-easydns/
.. _EdgeCenter DNS: https://edgecenter.ru/dns/
.. _octodns_edgecenter: https://github.com/octodns/octodns-edgecenter/
.. _Fastly: https://www.fastly.com/de/
.. _Financial-Times/octodns-fastly: https://github.com/Financial-Times/octodns-fastly
.. _G-Core Labs DNS: https://gcorelabs.com/dns/
.. _octodns_gcore: https://github.com/octodns/octodns-gcore/
.. _Gandi: https://www.gandi.net/en-US/domain/dns
.. _octodns_gandi: https://github.com/octodns/octodns-gandi/
.. _Google Cloud DNS: https://cloud.google.com/dns
.. _octodns_googlecloud: https://github.com/octodns/octodns-googlecloud/
.. _Hetzner DNS: https://www.hetzner.com/dns-console
.. _octodns_hetzner: https://github.com/octodns/octodns-hetzner/
.. _Infoblox: https://www.infoblox.com/
.. _asyncon/octoblox: https://github.com/asyncon/octoblox
.. _Infomaniak: https://www.infomaniak.com/
.. _octodns_infomaniak: https://github.com/M0NsTeRRR/octodns-infomaniak
.. _Lexicon: https://dns-lexicon.github.io/dns-lexicon/#
.. _dns-lexicon/dns-lexicon: https://github.com/dns-lexicon/dns-lexicon
.. _Mythic Beasts DNS: https://www.mythic-beasts.com/support/hosting/dns
.. _octodns_mythicbeasts: https://github.com/octodns/octodns-mythicbeasts/
.. _NetBox-DNS Plugin: https://github.com/peteeckel/netbox-plugin-dns
.. _olofvndrhr/octodns-netbox-dns: https://github.com/olofvndrhr/octodns-netbox-dns
.. _NS1: https://ns1.com/products/managed-dns
.. _octodns_ns1: https://github.com/octodns/octodns-ns1/
.. _OVHcloud DNS: https://www.ovhcloud.com/en/domains/dns-subdomain/
.. _octodns_ovh: https://github.com/octodns/octodns-ovh/
.. _Pi-hole: https://pi-hole.net/
.. _jvoss/octodns-pihole: https://github.com/jvoss/octodns-pihole
.. _PowerDNS: https://www.powerdns.com/
.. _octodns_powerdns: https://github.com/octodns/octodns-powerdns/
.. _Rackspace: https://www.rackspace.com/library/what-is-dns
.. _octodns_rackspace: https://github.com/octodns/octodns-rackspace/
.. _Scaleway: https://www.scaleway.com/en/dns/
.. _octodns_scaleway: https://github.com/scaleway/octodns-scaleway
.. _Selectel: https://selectel.ru/en/services/additional/dns/
.. _octodns_selectel: https://github.com/octodns/octodns-selectel/
.. _SPF Value Management: https://github.com/octodns/octodns-spf
.. _octodns_spf: https://github.com/octodns/octodns-spf/
.. _TransIP: https://www.transip.eu/knowledgebase/entry/155-dns-and-nameservers/
.. _octodns_transip: https://github.com/octodns/octodns-transip/
.. _UltraDNS: https://vercara.com/authoritative-dns
.. _octodns_ultra: https://github.com/octodns/octodns-ultra/
.. _YamlProvider: /octodns/provider/yaml.py
.. _kompetenzbolzen/octodns-custom-provider: https://github.com/kompetenzbolzen/octodns-custom-provider

Sources
-------

Similar to providers, but can only serve to populate records into a zone,
cannot be synced to.

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - Source/Module
     - Notes
   * - `AxfrSource (BIND)`_
     -
   * - `DDNS Source`_
     -
   * - `EnvVarSource`_
     - read-only environment variable injection
   * - `Lexicon Source`_
     -
   * - `Netbox Source`_
     -
   * - `PHPIPAM Source`_
     -
   * - `TinyDnsFileSource`_
     -
   * - `ZoneFileSource`_
     -

.. _AxfrSource (BIND): https://github.com/octodns/octodns-bind/
.. _DDNS Source: https://github.com/octodns/octodns-ddns
.. _EnvVarSource: /octodns/source/envvar.py
.. _Lexicon Source: https://github.com/doddo/octodns-lexicon
.. _Netbox Source: https://github.com/sukiyaki/octodns-netbox
.. _PHPIPAM Source: https://github.com/kompetenzbolzen/octodns-custom-provider
.. _TinyDnsFileSource: /octodns/source/tinydns.py
.. _ZoneFileSource: https://github.com/octodns/octodns-bind/

Processors
----------

.. list-table::
   :header-rows: 1

   * - Processor
     - Description
   * - `AcmeManagingProcessor`_
     - Useful when processes external to octoDNS are managing acme challenge DNS records, e.g. LetsEncrypt
   * - `AutoArpa`_
     - See :ref:`automatic-ptr-generation`
   * - `EnsureTrailingDots`_
     - Processor that ensures ALIAS, CNAME, DNAME, MX, NS, PTR, and SRVs have trailing dots
   * - `ExcludeRootNsChanges`_
     - Filter that errors or warns on planned root/APEX NS records changes.
   * - `IgnoreRootNsFilter`_
     - Filter that IGNORES root/APEX NS records and prevents octoDNS from trying to manage them (where supported.)
   * - `MetaProcessor`_
     - Adds a special meta record with timing, UUID, providers, and/or version to aid in debugging and monitoring.
   * - `NameAllowlistFilter`_
     - Filter that ONLY manages records that match specified naming patterns, all others will be ignored
   * - `NameRejectlistFilter`_
     - Filter that IGNORES records that match specified naming patterns, all others will be managed
   * - `ValueAllowlistFilter`_
     - Filter that ONLY manages records that match specified value patterns based on `rdata_text`, all others will be ignored
   * - `ValueRejectlistFilter`_
     - Filter that IGNORES records that match specified value patterns based on `rdata_text`, all others will be managed
   * - `OwnershipProcessor`_
     - Processor that implements ownership in octoDNS so that it can manage only the records in a zone in sources and will ignore all others.
   * - `SpfDnsLookupProcessor`_
     - Processor that checks SPF values for violations of DNS query limits
   * - `TtlRestrictionFilter`_
     - Processor that restricts the allow TTL values to a specified range or list of specific values
   * - `TypeAllowlistFilter`_
     - Filter that ONLY manages records of specified types, all others will be ignored
   * - `TypeRejectlistFilter`_
     - Filter that IGNORES records of specified types, all others will be managed
   * - `octodns-spf`_
     - SPF Value Management for octoDNS

.. _AcmeManagingProcessor: https://github.com/octodns/octodns/tree/main/octodns/processor/acme.py)
.. _AutoArpa: https://github.com/octodns/octodns/tree/main/octodns/processor/arpa.py)
.. _EnsureTrailingDots: https://github.com/octodns/octodns/tree/main/octodns/processor/trailing_dots.py)
.. _ExcludeRootNsChanges: https://github.com/octodns/octodns/tree/main/octodns/processor/filter.py)
.. _IgnoreRootNsFilter: https://github.com/octodns/octodns/tree/main/octodns/processor/filter.py)
.. _MetaProcessor: https://github.com/octodns/octodns/tree/main/octodns/processor/meta.py)
.. _NameAllowlistFilter: https://github.com/octodns/octodns/tree/main/octodns/processor/filter.py)
.. _NameRejectlistFilter: https://github.com/octodns/octodns/tree/main/octodns/processor/filter.py)
.. _ValueAllowlistFilter: https://github.com/octodns/octodns/tree/main/octodns/processor/filter.py)
.. _ValueRejectlistFilter: https://github.com/octodns/octodns/tree/main/octodns/processor/filter.py)
.. _OwnershipProcessor: https://github.com/octodns/octodns/tree/main/octodns/processor/ownership.py)
.. _SpfDnsLookupProcessor: https://github.com/octodns/octodns/tree/main/octodns/processor/spf.py)
.. _TtlRestrictionFilter: https://github.com/octodns/octodns/tree/main/octodns/processor/restrict.py)
.. _TypeAllowlistFilter: https://github.com/octodns/octodns/tree/main/octodns/processor/filter.py)
.. _TypeRejectlistFilter: https://github.com/octodns/octodns/tree/main/octodns/processor/filter.py)
.. _octodns-spf: https://github.com/octodns/octodns/tree/main//github.com/octodns/octodns-spf)

Custom Sources and Providers
----------------------------

You can check out the source_ and provider_ directories to see what's currently
supported.  Sources act as a source of record information. AxfrSource and
TinyDnsFileSource are currently the only OSS sources, though we have several
others internally that are specific to our environment. These include something
to pull host data from gPanel_ and a similar provider that sources information
about our network gear to create both ``A`` & ``PTR`` records for their
interfaces. Things that might make good OSS sources might include an
``ElbSource`` that pulls information about `AWS Elastic Load Balancers`_ and
dynamically creates ``CNAME``s for them, or ``Ec2Source`` that pulls instance
information so that records can be created for hosts similar to how our
``GPanelProvider`` works.

.. _source: https://github.com/octodns/octodns/tree/main/octodns/source/
.. _provider: https://github.com/octodns/octodns/tree/main/octodns/provider/
.. _gPanel: https://githubengineering.com/githubs-metal-cloud/
.. _AWS Elastic Load Balancers: https://aws.amazon.com/elasticloadbalancing/

Most of the things included in octoDNS are providers, the obvious difference
being that they can serve as both sources and targets of data. We'd really like
to see this list grow over time so if you use an unsupported provider then PRs
are welcome. The existing providers should serve as reasonable examples. Those
that have no GeoDNS support are relatively straightforward. Unfortunately most
of the APIs involved to do GeoDNS style traffic management are complex and
somewhat inconsistent so adding support for that function would be nice, but is
optional and best done in a separate pass.

The ``class`` key in the providers config section can be used to point to
arbitrary classes in the python path so internal or 3rd party providers can
easily be included with no coordination beyond getting them into
``PYTHONPATH``, most likely installed into the virtualenv with octoDNS.

For examples of building third-party sources and providers, see `Related
Projects and Resources`_

Contributing
------------

Please see our contributing_ document if you would like to participate!

.. _contributing: https://github.com/octodns/octodns/tree/main/CONTRIBUTING.md

Getting help
------------

If you have a problem or suggestion, please `open an issue`_ in this repository, and
we will do our best to help.

Please note that this project adheres to the `Contributor Covenant Code of
Conduct`_.

.. _open an issue: https://github.com/octodns/octodns/issues/new
.. _Contributor Covenant Code of Conduct: https://github.com/octodns/octodns/tree/main/CODE_OF_CONDUCT.md

Related Projects and Resources
------------------------------

* GitHub Action: `octoDNS-Sync`_
* NixOS Integration: `NixOS-DNS`_
* Sample Implementations, see how others are using it

  - `hackclub/dns`_
  - `kubernetes/k8s.io:/dns`_
  - `g0v-network/domains`_
  - `jekyll/dns`_

* Resources

  - Article: `Visualising DNS records with Neo4j`_ + code
  - Video: `FOSDEM 2019 - DNS as code with octodns`_
  - GitHub Blog: `Enabling DNS split authority with octoDNS`_
  - Tutorial: `How To Deploy and Manage Your DNS using octoDNS on Ubuntu 18.04`_
  - Cloudflare Blog: `Improving the Resiliency of Our Infrastructure DNS Zone`_

.. _octoDNS-Sync: https://github.com/marketplace/actions/octodns-sync
.. _NixOS-DNS: https://github.com/Janik-Haag/nixos-dns/
.. _hackclub/dns: https://github.com/hackclub/dns)
.. _`kubernetes/k8s.io:/dns`: https://github.com/kubernetes/k8s.io/tree/main/dns)
.. _g0v-network/domains: https://github.com/g0v-network/domains)
.. _jekyll/dns: https://github.com/jekyll/dns)
.. _Visualising DNS records with Neo4j: https://medium.com/@costask/querying-and-visualising-octodns-records-with-neo4j-f4f72ab2d474
.. _FOSDEM 2019 - DNS as code with octodns: https://archive.fosdem.org/2019/schedule/event/dns_octodns/
.. _Enabling DNS split authority with octoDNS: https://github.blog/2017-04-27-enabling-split-authority-dns-with-octodns/
.. _How To Deploy and Manage Your DNS using octoDNS on Ubuntu 18.04: https://www.digitalocean.com/community/tutorials/how-to-deploy-and-manage-your-dns-using-octodns-on-ubuntu-18-04
.. _Improving the Resiliency of Our Infrastructure DNS Zone: https://blog.cloudflare.com/improving-the-resiliency-of-our-infrastructure-dns-zone/

If you know of any other resources, please do let us know!

License
-------

octoDNS is licensed under the `MIT license`_.

.. _MIT license: https://github.com/octodns/octodns/tree/mainLICENSE

The MIT license grant is not for GitHub's trademarks, which include the logo
designs. GitHub reserves all trademark and copyright rights in and to all
GitHub trademarks. GitHub's logos include, for instance, the stylized designs
that include "logo" in the file title in the following folder:
https://github.com/octodns/octodns/tree/main/docs/logos/

GitHub® and its stylized versions and the Invertocat mark are GitHub's
Trademarks or registered Trademarks. When using GitHub's logos, be sure to
follow the GitHub logo guidelines.

Authors
-------

octoDNS was designed and authored by `Ross McFarland`_ and `Joe Williams`_. See
https://github.com/octodns/octodns/graphs/contributors for a complete list of
people who've contributed.

.. _Ross McFarland: https://github.com/ross
.. _Joe Williams: https://github.com/joewilliams
