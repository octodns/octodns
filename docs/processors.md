# octoDNS processors

## Available processors

These are listed in the main [`README`](../README.md#processors)

## Configuring processors

Configuring processors is done in the main config file.

### Defining a processor configuration

This is done under the top-level `processors` key in the octoDNS config file (for example `config.yaml`), as a sibling to the `manager` key.

The `processors` key contains YAML objects, where the key is the name of the processor, and the `class` value within that object refers to the processor name.

For example, to define a provider called `custom_meta` using the [`MetaProcessor`](../octodns/processor/meta.py) in order to extend the default `include_meta` behaviour:

```yaml
manager:
    include_meta: false # disable default, basic `meta` records
processors:
    custom_meta:
        class: octodns.processor.meta.MetaProcessor
        record_name: meta
        include_time: true
        include_uuid: true
        include_provider: true
        include_version: false
```

**NOTE:** the specific parameters for each processor are only documented within [the code](../octodns/processor/)

### Utilising the processor configuration

#### On **individual** domains

Each domain can utilise the processor independently by adding the name of the defined processor to a `processors` key beneath a `zone`:

```yaml
zones:
    example.com.:
        source:
            - yaml_config
        target:
            - hetzner
        processors:
            - custom_meta
```

#### On **all** domains

To utilise the processor on **all** domains automatically, including new domains added to the `zones` config in future then you can add this to the `processors` key under the `manager` section of the configuration:

```yaml
manager:
    processors:
        - custom_meta
```
