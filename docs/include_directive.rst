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

Array Syntax
............

The ``!include`` directive also supports an array syntax to merge multiple files
together. This is useful for composing configurations from multiple sources.

Merging Dictionaries
~~~~~~~~~~~~~~~~~~~~~

When including multiple files that contain dictionaries, the dictionaries are
merged together. Later files override keys from earlier files::

  ---
  # main.yaml
  merged-config: !include
    - base-config.yaml
    - overrides.yaml

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
    'added': 'hi'       # added by overrides
  }

Merging Arrays
~~~~~~~~~~~~~~

When including multiple files that contain arrays, the arrays are concatenated
together::

  ---
  # main.yaml
  all-values: !include
    - values-1.yaml
    - values-2.yaml

If ``values-1.yaml`` contains::

  ---
  - item1
  - item2

And ``values-2.yaml`` contains::

  ---
  - item3
  - item4

Then ``all-values`` will be ``['item1', 'item2', 'item3', 'item4']``.

Empty Arrays
~~~~~~~~~~~~

An empty array can be used with ``!include``, which results in ``null``::

  ---
  empty-value: !include []

This sets ``empty-value`` to ``null``.

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
    base-config: !include providers/common.yaml

    route53:
      class: octodns_route53.Route53Provider
      access_key_id: env/AWS_ACCESS_KEY_ID
      secret_access_key: env/AWS_SECRET_ACCESS_KEY
      # Include common retry/timeout settings
      settings: !include providers/aws-settings.yaml

Shared Zone Configuration::

  ---
  # config.yaml
  zones:
    example.com.: &standard-setup !include zones/standard-setup.yaml
    example.net.: *standard-setup
    example.org.: *standard-setup

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

Where ``common/apex.yaml`` might contain::

  ---
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

Common Record Values
~~~~~~~~~~~~~~~~~~~~

You can merge multiple files to build up complex record sets::

  ---
  # zone.yaml
  '':
    type: TXT
    values: !include
      - txt-records/verification.yaml
      - txt-records/spf.yaml
      - txt-records/dmarc.yaml

This combines TXT records from multiple files into a single record set.

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

When using the array syntax to include multiple files, all files must contain
compatible types:

* All files must contain **dictionaries**, or
* All files must contain **arrays**

If the first file contains a dictionary and a subsequent file contains an array
(or vice versa), octoDNS will raise a ``ConstructorError`` with a clear message
indicating which file and position caused the type mismatch.

Simple scalar values (strings, numbers, booleans) are not supported with the
array syntax. Use single file includes for scalar values.

Examples
--------

Example 1: Shared Provider Settings
....................................

Create reusable provider configurations::

  # providers/retry-settings.yaml
  ---
  max_retries: 5
  retry_delay: 2
  timeout: 30

  # production.yaml
  ---
  providers:
    dacloud:
      class: octodns_route53.DaCloudProvider
      access_key_id: env/DC_ACCESS_KEY_ID
      secret_access_key: env/DC_SECRET_ACCESS_KEY
      network: !include providers/retry-settings.yaml

Example 2: Composing TXT Records
.................................

Build TXT records from multiple sources::

  # txt-records/spf.yaml
  ---
  - "v=spf1 include:_spf.google.com ~all"

  # txt-records/verification.yaml
  ---
  - "google-site-verification=abc123"
  - "ms-domain-verification=xyz789"

  # example.com.yaml
  ---
  '':
    type: TXT
    values: !include
      - txt-records/spf.yaml
      - txt-records/verification.yaml

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