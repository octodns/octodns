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
    # Replace duplicate records rather than throw an error, default is False
    # which throws an error
    replace: False
    # Explicitly set the TTL of auto-created records, default is 3600s, 1hr
    ttl: 1800
```

Once enabled a singleton `AutoArpa` instance, `auto-arpa`, will be added to the pool of providers and globally configured to run as the very last global processor so that it will see all records as they will be seen by targets. Further all zones ending with `arpa.` will be held back and processed after all other zones have been completed so that all `A` and `AAAA` records will have been seen prior to planning the `arpa.` zones. 

In order to add `PTR` records for a zone the `auto-arpa` source should be added to the list of sources for the zone.

```yaml
0.0.10.in-addr.arpa.:
  sources:
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

  powerdns:
    class: octodns_powerdns.PowerDnsProvider
    host: 10.0.0.53
    port: 8081
    api_key: env/POWERDNS_API_KEY

zones:
  exxampled.com.:
    sources:
      - config
    targets:
      - powerdns

  0.0.10.in-addr.arpa.:
    sources:
      - auto-arpa
    targets:
      - powerdns
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
