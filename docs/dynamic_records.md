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

#### Route53 Health Check Options

| Key  | Description | Default |
|--|--|--|
| measure_latency | Show latency in AWS console | true |
| request_interval | Healthcheck interval [10\|30] seconds | 10 |

```yaml

---
  octodns:
    healthcheck:
      host: my-host-name
      path: /dns-health-check
      port: 443
      protocol: HTTPS
    route53:
      healthcheck:
        measure_latency: false
        request_interval: 30
```

#### Constellix Health Check Options

| Key  | Description | Default |
|--|--|--|
| sonar_interval | Sonar check interval | ONEMINUTE |
| sonar_port | Sonar check port | 80 |
| sonar_regions | Sonar check regions for a check. WORLD or a list of values | WORLD |
| sonar_type | Sonar check type TCP/HTTP | TCP |

Sonar check interval (sonar_interval) possible values:

* FIVESECONDS
* THIRTYSECONDS
* ONEMINUTE
* TWOMINUTES
* THREEMINUTES
* FOURMINUTES
* FIVEMINUTES
* TENMINUTES
* THIRTYMINUTES
* HALFDAY
* DAY

Sonar check regions (sonar_regions) possible values:

* ASIAPAC
* EUROPE
* NACENTRAL
* NAEAST
* NAWEST
* OCEANIA
* SOUTHAMERICA

```yaml

---
  octodns:
    constellix:
      healthcheck:
        sonar_interval: DAY
        sonar_port: 80
        sonar_regions:
        - ASIAPAC
        - EUROPE
        sonar_type: TCP
```

#### NS1 Health Check Options

| Key  | Description | Default |
|--|--|--|
| policy | One of:<ol><li>`all` - down if every region is down</li><li>`quorum` - down if majority regions are down</li><li>`one` - down if any region is down</ol> | `quorum` |
| frequency | Frequency (in seconds) of health-check | 60 |
| connect_timeout | Timeout (in seconds) before we give up trying to connect | 2 |
| response_timeout | Timeout (in seconds) after connecting to wait for output | 10 |
| rapid_recheck | Enable or disable a second, automatic verification test before changing the status of a host. Enabling this option can help prevent false positives. | False |

```yaml

---
  octodns:
    ns1:
      healthcheck:
        policy: quorum
        frequency: 60
        connect_timeout: 2
        response_timeout: 10
        rapid_recheck: True
```

#### [Azure Health Check Options](https://docs.microsoft.com/en-us/azure/traffic-manager/traffic-manager-monitoring#configure-endpoint-monitoring)

| Key                          | Description                                                  | Default |
| ---------------------------- | ------------------------------------------------------------ | ------- |
| interval_in_seconds          | This value specifies how often an endpoint is checked for its health  from a Traffic Manager probing agent. You can specify two values here:  30 seconds (normal probing) and 10 seconds (fast probing). If no values  are provided, the profile sets to a default value of 30 seconds. Visit  the [Traffic Manager Pricing](https://azure.microsoft.com/pricing/details/traffic-manager) page to learn more about fast probing pricing. | 30      |
| timeout_in_seconds           | This property specifies the amount of time the Traffic Manager probing  agent should wait before considering a health probe check to an endpoint a failure. If the Probing Interval is set to 30 seconds, then you can  set the Timeout value between 5 and 10 seconds. If no value is  specified, it uses a default value of 10 seconds. If the Probing  Interval is set to 10 seconds, then you can set the Timeout value  between 5 and 9 seconds. If no Timeout value is specified, it uses a  default value of 9 seconds. | 10 or 9 |
| tolerated_number_of_failures | This value specifies how many failures a Traffic Manager probing agent  tolerates before marking that endpoint as unhealthy. Its value can range between 0 and 9. A value of 0 means a single monitoring failure can  cause that endpoint to be marked as unhealthy. If no value is specified, it uses the default value of 3. | 3       |

```
---
  octodns:
    azuredns:
      healthcheck:
        interval_in_seconds: 10
        timeout_in_seconds: 7
        tolerated_number_of_failures: 4
```
