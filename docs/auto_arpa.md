## Automatic PTR Generation With auto_arpa

octoDNS supports the automatic generation of `PTR` records for in-addr.arpa. and ip6.arpa. zones. In order to enable the functionality the `auto_arpa` key needs to be passed to the manager configuration.

```yaml
---
manager:
  auto_arpa: true
```

Alternatively the value can be a dictionary with configuration options for the AutoArpa processor/provider.

```yaml
---
manager:
  auto_arpa:
    # Whether duplicate records should replace rather than error
    # (optiona, default False)
    populate_should_replace: false
    # Explicitly set the TTL of auto-created records, default is 3600s, 1hr
    ttl: 1800
```

Once enabled, a singleton `AutoArpa` instance, `auto-arpa`, will be added to the pool of providers and globally configured to run as the very last global processor so that it will see all records as they will be seen by targets. Further all zones ending with `arpa.` will be held back and processed after all other zones have been completed so that all `A` and `AAAA` records will have been seen prior to planning the `arpa.` zones.

In order to add `PTR` records for a zone the `auto-arpa` source should be added to the list of sources for the zone.

```yaml
# Zones are matched on suffix so `0.10.in-addr.arpa.` would match anything
# under `10.0/16` or `0.8.e.f.ip6-.arpa.` would match any IPv6 address under
# `fe80::`, 0.0.10 here matches 10.0.0/24.
0.0.10.in-addr.arpa.:
  sources:
    # In most cases you'll have some statically configured records combined in
    # with the auto-generated records as shown here, but that's not strictly
    # required and this could just be `auto-arpa`.
    # would throw an DuplicateRecordException.
    - config
    - auto-arpa
  targets:
    - ...
```

The above will add `PTR` records for any `A` records previously seen with IP addresses 10.0.0.*.

### A Complete Example

#### config/octodns.yaml

```yaml
manager:
  auto_arpa: true

providers:
  config:
    class: octodns.provider.yaml.YamlProvider
    directory: tests/config

  route53:
    class: octodns_route53.Route53Provider
    access_key_id: env/AWS_ACCESS_KEY_ID
    secret_access_key: env/AWS_SECRET_ACCESS_KEY

zones:
  exxampled.com.:
    sources:
      - config
    targets:
      - route53

  0.0.10.in-addr.arpa.:
    sources:
      - auto-arpa
    targets:
      - route53
```

#### config/exxampled.com.yaml

```yaml
? ''
: type: A
  values:
  - 10.0.0.101
  - 10.0.0.102
email:
  type: A
  value: 10.0.0.103
fileserver:
  type: A
  value: 10.0.0.103
```

#### Auto-generated PTRs

* 101.0.0.10: exxampled.com.
* 102.0.0.10: exxampled.com.
* 103.0.0.10: email.exxampled.com., fileserver.exxampled.com.

### Notes

Automatic `PTR` generation requires a "complete" picture of records and thus cannot be done during partial syncs. Thus syncing `arpa.` zones will throw an error any time filtering of zones, targets, or sources is being done.

#### AutoArpa and Dynamic Zone Config

The AutoArpa provider works with Dynamic Zone Config, but only in the sense that it doesn't stop it from working. It requires another provider to actually generate the list of zones. It could be the Yaml provider like so:

```yaml
example.com.:
  sources:
    - config
  targets:
    - ...
"*.arpa.":
  sources:
    - config
    - auto-arpa
  targets:
    - ...
```
That would take all the relevant records from example.com and add them as PTR records for the arpa zones in the same place as the 'config' source specifies.
