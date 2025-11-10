YAML !include Directive
=======================

The ``!include`` directive is a powerful feature in octoDNS that allows you to
reuse YAML content across multiple configuration files and zone files. This
helps reduce duplication and makes your DNS configuration more maintainable.

Overview
--------

The ``!include`` directive can be used anywhere in your YAML files to include
content from other files. Files are resolved relative to the directory
containing the file with the ``!include`` directive.

Basic Usage
-----------

Single File Include
...................

The simplest form includes the entire contents of a single file::

  ---
  # main.yaml
  common-config: !include common.yaml

If ``common.yaml`` contains::

  ---
  key: value
  setting: 42

Then ``common-config`` will be set to ``{'key': 'value', 'setting': 42}``.

The included file can contain any valid YAML type: dictionaries, lists, strings,
numbers, or even ``null`` values.

Merge Syntax
............

The ``!include`` directive can also be used with the merge operator, ``<<:``.
This is useful for composing configurations from multiple sources.

Merging Dictionaries
~~~~~~~~~~~~~~~~~~~~

When including multiple files that contain dictionaries, the dictionaries are
merged together. Later files override keys from earlier files::

  ---
  # main.yaml
  merged-config:
    <<: !include base-config.yaml
    <<: !include overrides.yaml
    key: value

If ``base-config.yaml`` contains::

  ---
  timeout: 30
  retries: 3
  debug: false

And ``overrides.yaml`` contains::

  ---
  timeout: 60
  debug: true
  added: hi

Then ``merged-config`` will be::

  {
    'timeout': 60,      # overridden
    'retries': 3,       # from base
    'debug': true,      # overridden
    'added': 'hi',      # added by overrides
    'key': 'value',     # from main
  }

Use Cases
---------

Configuration Files
...................

The ``!include`` directive is useful in octoDNS configuration files for sharing
common provider settings, processor configurations, or zone settings.

Shared Provider Configuration::

  ---
  # production.yaml
  providers:
    # contents will be merged with what's defined here
    <<: !include providers/common.yaml

    route53:
      class: octodns_route53.Route53Provider
      access_key_id: env/AWS_ACCESS_KEY_ID
      secret_access_key: env/AWS_SECRET_ACCESS_KEY
      # Include common retry/timeout settings
      settings: !include providers/aws-settings.yaml

  ---
  # providers/common.yaml
  config:
    class: octodns.providers.yaml.YamlProvider
    directory: ./config/

  internal:
    class: octodns_powerdns.PdnsProvider
    ...

Shared Zone Configuration::

  ---
  # config.yaml
  zones:
    # contents will become the value for example.com.
    example.com.: &standard-setup !include zones/standard-setup.yaml
    example.net.: *standard-setup
    example.org.: *standard-setup

  ---
  # zones/standard-ssetup.yaml
  sources:
    - config
  targets:
    - internal
    - route53

Zone Files
..........

The ``!include`` directive is particularly powerful in zone files for reducing
duplication of common record configurations.

Shared APEX Records
~~~~~~~~~~~~~~~~~~~

When you have multiple zones with shared APEX records but differing records
otherwise, you can share the APEX configuration::

  ---
  # example.com.yaml
  '': !include common/apex.yaml
  api:
    type: A
    value: 1.2.3.4
  web:
    type: A
    value: 1.2.3.5


  ---
  # common/apex.yaml
  - type: A
    value: 1.2.3.4
  - type: MX
    values:
      - exchange: mail1.example.com.
        preference: 10
      - exchange: mail2.example.com.
        preference: 20
  - type: NS
    values:
      - 6.2.3.4.
      - 7.2.3.4.
  - type: TXT
    values:
      - some-domain-claiming-value=gimme
      - v=spf1 -all

Subdirectories
..............

Files in subdirectories can be included using relative paths::

  ---
  # main.yaml
  nested-config: !include subdir/nested.yaml
  deeper: !include subdir/another/deep.yaml
  parent: !include ../sibling/config.yaml

Type Requirements
-----------------

Any valid YAML datatype can be used in the basic **!include** stile.

When using the merge syntax all files must contain **dictionaries**.

      network: !include providers/retry-settings.yaml

Best Practices
--------------

1. **Organize shared files**: Create a dedicated directory structure for shared
   configurations (e.g., ``shared/``, ``common/``)

2. **Use descriptive filenames**: Name included files clearly to indicate their
   purpose (e.g., ``spf-record.yaml``, ``geo-routing-rules.yaml``)

3. **Keep includes shallow**: Avoid deeply nested includes as they can make
   the configuration harder to understand and debug

4. **Document shared files**: Add comments in shared files explaining their
   purpose and where they're used