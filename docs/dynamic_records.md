## Dynamic Record Support

Dynamic records provide support for GeoDNS and weighting to records. `A` and `AAAA` are fully supported and reasonably well tested for both Dyn (via Traffic Directors) and Route53. There is preliminary support for `CNAME` records, but caution should be exercised as they have not been thoroughly tested.

Configuring GeoDNS is complex and the details of the functionality vary widely from provider to provider. octoDNS has an opinionated view mostly to give a reasonably consistent behavior across providers which is similar to the overall philosophy and approach of octoDNS itself. It may not fit your needs or use cases, in which case please open an issue for discussion. We expect this functionality to grow and evolve over time as it's more widely used.

### An Annotated Example

```yaml

---
test:
  # This is a dynamic record when used with providers that support it
  dynamic:
    # These are the pools of records that can be referenced and thus used by rules
    pools:
      apac:
        # An optional fallback, if all of the records in this pool fail this pool should be tried
        fallback: na
        # One or more values for this pool
        values:
        - value: 1.1.1.1
        - value: 2.2.2.2
      eu:
        fallback: na
        values:
        - value: 3.3.3.3
          # Weight for this value, if omitted the default is 1
          weight: 2
        - value: 4.4.4.4
          weight: 3
      na:
        # Implicit fallback to the default pool (below)
        values:
        - value: 5.5.5.5
        - value: 6.6.6.6
        - value: 7.7.7.7
    # Rules that assign queries to pools
    rules:
    - geos:
      # Geos used in matching queries
      - AS
      - OC
      # The pool to service the query from
      pool: apac
    - geos:
      - AF
      - EU
      pool: eu
    # No geos means match all queries
    - pool: na
  ttl: 60
  type: A
  # These values become a non-healthchecked default pool
  values:
  - 5.5.5.5
  - 6.6.6.6
  - 7.7.7.7
```

#### Geo Codes

Geo codes consist of one to three parts depending on the scope of the area being targeted. Examples of these look like:

* 'NA-US-KY' - North America, United States, Kentucky
* 'NA-US' - North America, United States
* 'NA' - North America

The first portion is the continent:

* 'AF': 14,  # Continental Africa
* 'AN': 17,  # Continental Antarctica
* 'AS': 15,  # Continental Asia
* 'EU': 13,  # Continental Europe
* 'NA': 11,  # Continental North America
* 'OC': 16,  # Continental Australia/Oceania
* 'SA': 12,  # Continental South America

The second is the two-letter ISO Country Code https://en.wikipedia.org/wiki/ISO_3166-2 and the third is the ISO Country Code Subdivision as per https://en.wikipedia.org/wiki/ISO_3166-2:US. Change the code at the end for the country you are subdividing. Note that these may not always be supported depending on the providers in use.

### Health Checks

octoDNS will automatically configure the provider to monitor each IP and check for a 200 response for **https://<ip_address>/_dns**.

These checks can be customized via the `healthcheck` configuration options.

```yaml

---
test:
  ...
  octodns:
    healthcheck:
      host: my-host-name
      path: /dns-health-check
      port: 443
      protocol: HTTPS
  ...
```

| Key  | Description | Default |
|--|--|--|
| host | FQDN for host header and SNI | - |
| path | path to check | _dns |
| port | port to check | 443 |
| protocol | HTTP/HTTPS/TCP | HTTPS |

Healthchecks can also be skipped for individual pool values. These values can be forced to always-serve or never-serve using the `status` flag.

`status` flag is optional and accepts one of three possible values, `up`/`down`/`obey`, with `obey` being the default:

```yaml
test:
  ...
  dynamic:
    pools:
      na:
        values:
        - value: 1.2.3.4
          status: down
        - value: 2.3.4.5
          status: up
        - value: 3.4.5.6
          # defaults to status: obey
  ...
```

Support matrix:
* NS1 supports all 3 flag values
* Azure DNS supports only `obey` and `down`
* All other dynamic-capable providers only support the default `obey`

See "Health Check Options" in individual provider documentation for customization support.
