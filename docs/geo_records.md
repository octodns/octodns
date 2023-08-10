## Geo Record Support

Note: Geo DNS records are still supported for the time being, but it is still strongly encouraged that you look at [Dynamic Records](/docs/dynamic_records.md) instead as they are a superset of functionality.

GeoDNS is currently supported for `A` and `AAAA` records on the Dyn (via Traffic Directors) and Route53 providers. Records with geo information pushed to providers without support for them will be managed as non-geo records using the base values.

Configuring GeoDNS is complex and the details of the functionality vary widely from provider to provider. octoDNS has an opinionated view of how GeoDNS should be set up and does its best to map that to each provider's offering in a way that will result in similar behavior. It may not fit your needs or use cases, in which case please open an issue for discussion. We expect this functionality to grow and evolve over time as it's more widely used.

The following is an example of GeoDNS with three entries NA-US-CA, NA-US-NY, OC-AU. octoDNS creates another one labeled 'default' with the details for the actual A record, This default record is the failover record if the monitoring check fails.

```yaml
---
? ''
: type: TXT
  value: v=spf1 -all
test:
  geo:
    NA-US-NY:
    - 111.111.111.1
    NA-US-CA:
    - 111.111.111.2
    OC-AU:
    - 111.111.111.3
    EU:
    - 111.111.111.4
  ttl: 300
  type: A
  value: 111.111.111.5
```


The geo labels breakdown based on:

1.
    - 'AF': 14,  # Continental Africa
    - 'AN': 17,  # Continental Antarctica
    - 'AS': 15,  # Continental Asia
    - 'EU': 13,  # Continental Europe
    - 'NA': 11,  # Continental North America
    - 'OC': 16,  # Continental Australia/Oceania
    - 'SA': 12,  # Continental South America

2. ISO Country Code https://en.wikipedia.org/wiki/ISO_3166-2

3. ISO Country Code Subdivision as per https://en.wikipedia.org/wiki/ISO_3166-2:US   (change the code at the end for the country you are subdividing) * these may not always be supported depending on the provider.

So the example is saying:

- North America - United States - New York:  gets served an "A" record of  111.111.111.1
- North America - United States - California:   gets served an "A" record of  111.111.111.2
- Oceania - Australia: Gets served an "A" record of 111.111.111.3
- Europe: gets an "A" record of 111.111.111.4
- Everyone else gets an "A" record of 111.111.111.5

### Health Checks

octoDNS will automatically set up monitors check for a 200 response for **https://<ip_address>/_dns**.

These checks can be configured by adding a `healthcheck` configuration to the record:

```yaml
---
test:
  geo:
    AS:
      - 1.2.3.4
    EU:
      - 2.3.4.5
  octodns:
    healthcheck:
      host: my-host-name
      path: /dns-health-check
      port: 443
      protocol: HTTPS
```

| Key  | Description | Default |
|--|--|--|
| host | FQDN for host header and SNI | - |
| path | path to check | _dns |
| port | port to check | 443 |
| protocol | HTTP/HTTPS | HTTPS |

#### Route53 Healtch Check Options

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
