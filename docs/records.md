# OctoDNS records

## Record types

OctoDNS supports the following record types:

* `A`
* `AAAA`
* `CNAME`
* `MX`
* `NAPTR`
* `NS`
* `PTR`
* `SSHFP`
* `SPF`
* `SRV`
* `TXT`

Underlying provider support for each of these varies and some providers have extra requirements or limitations. In cases where a record type is not supported by a provider OctoDNS will ignore it there and continue to manage the record elsewhere. For example `SSHFP` is supported by Dyn, but not Route53. If your source data includes an SSHFP record OctoDNS will keep it in sync on Dyn, but not consider it when evaluating the state of Route53. The best way to find out what types are supported by a provider is to look for its `supports` method. If that method exists the logic will drive which records are supported and which are ignored. If the provider does not implement the method it will fall back to `BaseProvider.supports` which indicates full support.

Adding new record types to OctoDNS is relatively straightforward, but will require careful evaluation of each provider to determine whether or not it will be supported and the addition of code in each to handle and test the new type.

## GeoDNS support

GeoDNS is currently supported for `A` and `AAAA` records on the Dyn (via Traffic Directors) and Route53 providers. Records with geo information pushed to providers without support for them will be managed as non-geo records using the base values.

Configuring GeoDNS is complex and the details of the functionality vary widely from provider to provider. OctoDNS has an opinionated view of how GeoDNS should be set up and does its best to map that to each provider's offering in a way that will result in similar behavior. It may not fit your needs or use cases, in which case please open an issue for discussion. We expect this functionality to grow and evolve over time as it's more widely used.

The following is an example of GeoDNS with three entries NA-US-CA, NA-US-NY, OC-AU. Octodns creates another one labeled 'default' with the details for the actual A record, This default record is the failover record if the monitoring check fails.

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

3. ISO Country Code Subdevision as per https://en.wikipedia.org/wiki/ISO_3166-2:US   (change the code at the end for the country you are subdividing) * these may not always be supported depending on the provider.

So the example is saying:

- North America - United States - New York:  gets served an "A" record of  111.111.111.1
- North America - United States - California:   gets served an "A" record of  111.111.111.2
- Oceania - Australia: Gets served an "A" record of 111.111.111.3
- Europe: gets an "A" record of 111.111.111.4
- Everyone else gets an "A" record of 111.111.111.5


Octodns will automatically set up a monitor and check for **https://<ip_address>/_dns** and check for a 200 response.

## Config (`YamlProvider`)

OctoDNS records and `YamlProvider`'s schema is essentially a 1:1 match. Properties on the objects will match keys in the config.

### Names

Each top-level key in the yaml file is a record name. Two common special cases are the root record `''`, and a wildcard `'*'`.

```
---
'':
  type: A
  values:
    - 1.2.3.4
    - 1.2.3.5
'*':
  type: CNAME
  value: www.example.com.
www:
  type: A
  values:
    - 1.2.3.4
    - 1.2.3.5
www.sub:
  type: A
  values:
    - 1.2.3.6
    - 1.2.3.7
```

The above config lays out 4 records, `A`s for `example.com.`, `www.example.com.`, and `www.sub.example.com` and a wildcard `CNAME` mapping `*.example.com.` to `www.example.com.`.

### Multiple records

In the above example each name had a single record, but there are cases where a name will need to have multiple records associated with it. This can be accomplished by using a list.

```
---
'':
  - type: A
    values:
      - 1.2.3.4
      - 1.2.3.5
  - type: MX
    values:
      - priority: 10
        value: mx1.example.com.
      - priority: 10
        value: mx2.example.com.
```

### Record data

Each record type has a corresponding set of required data. The easiest way to determine what's required is probably to look at the record object in [`octodns/record.py`](/octodns/record.py). You may also utilize `octodns-validate` which will throw errors about what's missing when run.

`type` is required for all records. `ttl` is optional. When TTL is not specified the `YamlProvider`'s default will be used. In any situation where an array of `values` can be used you can opt to go with `value` as a single item if there's only one.
