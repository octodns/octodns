# octoDNS records

## Record types

octoDNS supports the following record types:

* `A`
* `AAAA`
* `ALIAS`
* `CAA`
* `CNAME`
* `DNAME`
* `LOC`
* `MX`
* `NAPTR`
* `NS`
* `PTR`
* `SPF`
* `SRV`
* `SSHFP`
* `TLSA`
* `TXT`
* `URLFWD`

Underlying provider support for each of these varies and some providers have extra requirements or limitations. In cases where a record type is not supported by a provider octoDNS will ignore it there and continue to manage the record elsewhere. For example `SSHFP` is supported by Dyn, but not Route53. If your source data includes an SSHFP record octoDNS will keep it in sync on Dyn, but not consider it when evaluating the state of Route53. The best way to find out what types are supported by a provider is to look for its `supports` method. If that method exists the logic will drive which records are supported and which are ignored. If the provider does not implement the method it will fall back to `BaseProvider.supports` which indicates full support.

Adding new record types to octoDNS is relatively straightforward, but will require careful evaluation of each provider to determine whether or not it will be supported and the addition of code in each to handle and test the new type.

## Advanced Record Support (GeoDNS, Weighting)

* [Dynamic Records](/docs/dynamic_records.md) - the preferred method for configuring geo-location, weights, and healthcheck based fallback between pools of services.
* [Geo Records](/docs/geo_records.md) - the original implementation of geo-location based records, now superseded by Dynamic Records (above)

## Config (`YamlProvider`)

octoDNS records and `YamlProvider`'s schema is essentially a 1:1 match. Properties on the objects will match keys in the config.

### Names

Each top-level key in the yaml file is a record name. Two common special cases are the root record `''`, and a wildcard `'*'`.

```yaml
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

```yaml
---
'':
  - type: A
    values:
      - 1.2.3.4
      - 1.2.3.5
  - type: MX
    values:
      - exchange: mx1.example.com.
        preference: 10
      - exchange: mx2.example.com.
        preference: 10
```

### Record data

Each record type has a corresponding set of required data. The easiest way to determine what's required is probably to look at the record object in [`octodns/record/__init__.py`](/octodns/record/__init__.py). You may also utilize `octodns-validate` which will throw errors about what's missing when run.

`type` is required for all records. `ttl` is optional. When TTL is not specified the `YamlProvider`'s default will be used. In any situation where an array of `values` can be used you can opt to go with `value` as a single item if there's only one.

### Lenience

octoDNS is fairly strict in terms of standards compliance and is opinionated in terms of best practices. Examples of the former include SRV record naming requirements and the latter that ALIAS records are constrained to the root of zones. The strictness and support of providers varies so you may encounter existing records that fail validation when you try to dump them or you may even have use cases for which you need to create or preserve records that don't validate. octoDNS's solution to this is the `lenient` flag.

It's best to think of the `lenient` flag as "I know what I'm doing and accept any problems I run across." The main reason being is that some providers may allow the non-compliant setup and others may not. The behavior of the non-compliant records may even vary from one provider to another. Caveat emptor.

#### octodns-dump

If you're trying to import a zone into octoDNS config file using `octodns-dump` which fails due to validation errors you can supply the `--lenient` argument to tell octoDNS that you acknowledge that things aren't lining up with its expectations, but you'd like it to go ahead anyway. This will do its best to populate the zone and dump the results out into an octoDNS zone file and include the non-compliant bits. If you go to use that config file octoDNS will again complain about the validation problems. You can correct them in cases where that makes sense, but if you need to preserve the non-compliant records read on for options.

#### Record level lenience

When there are non-compliant records configured in Yaml you can add the following to tell octoDNS to do it's best to proceed with them anyway. If you use `--lenient` above to dump a zone and you'd like to sync it as-is you can mark the problematic records this way.

```yaml
'not-root':
  octodns:
    lenient: true
  type: ALIAS
  values: something.else.com.
```

#### Zone level lenience

If you'd like to enable lenience for a whole zone you can do so with the following, thought it's strongly encouraged to mark things at record level when possible. The most common case where things may need to be done at the zone level is when using something other than `YamlProvider` as a source, e.g. syncing from `Route53Provider` to `Ns1Provider` when there are non-compliant records in the zone in Route53.

```yaml
  non-compliant-zone.com.:
    lenient: true
    sources:
    - route53
    targets:
    - ns1
```

#### Restrict Record manipulations

octoDNS currently provides the ability to limit the number of updates/deletes on
DNS records by configuring a percentage of allowed operations as a threshold.
If left unconfigured, suitable defaults take over instead. In the below example,
the Dyn provider is configured with limits of 40% on both update and
delete operations over all the records present.

````yaml
dyn:
    class: octodns.provider.dyn.DynProvider
    update_pcent_threshold: 0.4
    delete_pcent_threshold: 0.4
````

## Provider specific record types

### Creating and registering

octoDNS has support for provider specific record types through a dynamic type registration system. This functionality is powered by `Route.register_type` and can be used as follows.

```python
class _SpecificValue(object):
    ...

class SomeProviderSpecificRecord(ValuesMixin, Record):
    _type = 'SomeProvider/SPECIFIC'
    _value_type = _SpecificValue

Record.register_type(SomeProviderSpecificRecord)
```

Have a look in [octodns.record](/octodns/record/__init__.py) for examples of how records are implemented. `NsRecord` and `_NsValue` are fairly simple examples to start with. You can also take a look at [`Route53Provider`'s `Route53Provider/ALIAS` type](https://github.com/octodns/octodns-route53/blob/main/octodns_route53/record.py).

In general this support is intended for record types that only make sense for a single provider. If multiple providers have a similar record it may make sense to implement it in octoDNS core.

### Naming

By convention the record type should be prefixed with the provider class, e.g. `Route53Provider` followed by a `/` and an all-caps record type name `ALIAS`, e.g. `Route53Provider/ALIAS`.

### YamlProvider support

Once the type is registered `YamlProvider` will automatically gain support for it and they can be included in your zone yaml files.

```yaml
alias:
  type: Route53Provider/ALIAS
  values:
    - name: www
      type: A
    - name: www
      type: AAAA
```
