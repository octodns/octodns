Configuration
=============

Basics
------

This document picks up where :doc:`getting-started` and :doc:`records` leave off,
discussing details and less common scenarios.

YamlProvider
------------

:py:mod:`octodns.provider.yaml` lays out the options for configuring the most commonly
used source of record data.

Dynamic Zone Config
-------------------

In many cases octoDNS's dynamic zone configuration is the best option for
configuring octoDNS to manage your zones. In its simplest form that would look
something like::

  ---
  providers:
    config:
      class: octodns.provider.yaml.YamlProvider
      directory: ./config
      default_ttl: 3600
      enforce_order: True
    ns1:
      class: octodns_ns1.Ns1Provider
      api_key: env/NS1_API_KEY
    route53:
      class: octodns_route53.Route53Provider
      access_key_id: env/AWS_ACCESS_KEY_ID
      secret_access_key: env/AWS_SECRET_ACCESS_KEY

  zones:
    '*':
      sources:
        - config
      targets:
        - ns1
        - route53

This configuration will query both ns1 and route53 for the list of zones they
are managing and dynamically add them to the list being managed using the
sources and targets corresponding to the '*' section. See
:ref:`dynamic-zone-config` for details.

Static Zone Config
------------------

In cases where fine grained control is desired and the configuration of
individual zones varies ``zones`` can be an explicit list with each configured
zone listed along with its specific setup. As exemplified below ``alias`` zones
can be useful when two zones are exact copies of each other, with the same
configuration and records. YAML anchors are also helpful to avoid duplication
where zones share config, but not records.::

  ---
  manager:
    include_meta: True
    max_workers: 2

  providers:
    config:
      class: octodns.provider.yaml.YamlProvider
      directory: ./config
      default_ttl: 3600
      enforce_order: True
    ns1:
      class: octodns_ns1.Ns1Provider
      api_key: env/NS1_API_KEY
    route53:
      class: octodns_route53.Route53Provider
      access_key_id: env/AWS_ACCESS_KEY_ID
      secret_access_key: env/AWS_SECRET_ACCESS_KEY

  zones:
    example.com.: &dual_target
      sources:
        - config
      targets:
        - ns1
        - route53

    # these have the same setup as example.com., but will have their own files
    # in the configuration directory for records.
    third.tv.: *dual_target
    fourth.tv.: *dual_target

    example.net.:
      # example.net. is an exact copy of example.com., there will not be an
      # example.net.yaml file in the config directory as `alias` includes
      # duplicating the records of the aliased zone along with its config.
      alias: example.com.

    other.com.:
      lenient: True
      sources:
        - config
      targets:
        - ns1

General Configuration Concepts
------------------------------

``class`` is a special key that tells octoDNS what python class should be
loaded.  Any other keys will be passed as configuration values to that
provider. In general any sensitive or frequently rotated values should come
from environmental variables. When octoDNS sees a value that starts with
``env/`` it will look for that value in the process's environment and pass the
result along.

Further information can be found in the docstring of each source and provider
class.

The ``include_meta`` key in the ``manager`` section of the config controls the
creation of a TXT record at the root of a zone that is managed by octoDNS. If
set to ``True``, octoDNS will create a TXT record for the root of the zone with
the value ``provider=<target-provider>``. If not specified, the default value for
``include_meta`` is ``False``.

The ``max_workers`` key in the ``manager`` section of the config enables threading
to parallelize the planning portion of the sync.

``lenient``
-----------

``lenient`` mostly focuses on the details of ``Record``s and standards
compliance.  When set to ``true`` octoDNS will allow non-compliant
configurations & values where possible. For example CNAME values that don't end
with a ``.``, label length restrictions, and invalid geo codes on ``dynamic``
records. When in lenient mode octoDNS will log validation problems at
``WARNING`` and try and continue with the configuration or source data as it
exists. See Lenience_ for more information on the concept and how it can be
configured. For more targeted control — selectively disabling specific checks
or adding custom validation rules — see `Validators`_ below.

.. _Lenience: records.rst#lenience

Validators
----------

octoDNS ships with a suite of built-in validators that check records for
correctness (valid TTLs, well-formed values, healthcheck protocol names, etc.)
before any changes are applied. The validator system supports: enabling
validator sets, adding custom validators, disabling individual validators,
and registering validators programmatically from third-party code.

Validator sets and ``manager.enabled``
.......................................

Validators belong to named *sets*. ``manager.enabled`` controls which sets
are active for a run (default: ``['legacy']``)::

  manager:
    enabled:
      - legacy

All built-in validators belong to the ``legacy`` set. Omitting
``manager.enabled`` is equivalent to ``enabled: [legacy]`` and preserves the
original octoDNS behaviour.

Additional opt-in sets can be enabled alongside ``legacy``::

  manager:
    enabled:
      - legacy
      - rfc

A validator can belong to multiple sets; it becomes active when any of its
sets is listed in ``manager.enabled``.

Setting ``enabled: []`` activates only validators whose ``sets`` is ``None``
(see `Attaching validators programmatically`_ below).

Built-in validator ids
......................

Each built-in validator has a stable short id. All belong to the ``legacy``
set and can be disabled individually with ``manager.disable_validators``.

+----------------------+------------------------------------------+
| id                   | description                              |
+======================+==========================================+
| ``name``             | Record name format                       |
+----------------------+------------------------------------------+
| ``ttl``              | TTL range (positive integer)             |
+----------------------+------------------------------------------+
| ``healthcheck``      | Octodns healthcheck config fields        |
+----------------------+------------------------------------------+
| ``cname-root``       | CNAME must not be at zone root           |
+----------------------+------------------------------------------+
| ``alias-root``       | ALIAS must not be at zone root           |
+----------------------+------------------------------------------+
| ``srv-name``         | SRV name format                          |
+----------------------+------------------------------------------+
| ``uri-name``         | URI name format                          |
+----------------------+------------------------------------------+
| ``geo``              | Geo routing config                       |
+----------------------+------------------------------------------+
| ``dynamic``          | Dynamic routing config                   |
+----------------------+------------------------------------------+
| ``ip-value``         | A / AAAA value format                    |
+----------------------+------------------------------------------+
| ``caa-value``        | CAA rdata format                         |
+----------------------+------------------------------------------+
| ``mx-value``         | MX rdata format                          |
+----------------------+------------------------------------------+
| ``target-value``     | CNAME/ALIAS/DNAME/PTR target format      |
+----------------------+------------------------------------------+
| ``targets-value``    | NS targets format                        |
+----------------------+------------------------------------------+
| ``sshfp-value``      | SSHFP algorithm/fingerprint format       |
+----------------------+------------------------------------------+
| ``srv-value``        | SRV rdata format                         |
+----------------------+------------------------------------------+
| ``uri-value``        | URI rdata format                         |
+----------------------+------------------------------------------+
| ``naptr-value``      | NAPTR rdata format                       |
+----------------------+------------------------------------------+
| ``loc-value``        | LOC rdata format                         |
+----------------------+------------------------------------------+
| ``ds-value``         | DS rdata format                          |
+----------------------+------------------------------------------+
| ``tlsa-value``       | TLSA rdata format                        |
+----------------------+------------------------------------------+
| ``openpgpkey-value`` | OPENPGPKEY rdata format                  |
+----------------------+------------------------------------------+
| ``urlfwd-value``     | URLFWD rdata format                      |
+----------------------+------------------------------------------+
| ``svcb-value``       | SVCB rdata format                        |
+----------------------+------------------------------------------+
| ``https-value``      | HTTPS rdata format                       |
+----------------------+------------------------------------------+
| ``chunked-value``    | TXT/SPF chunk size                       |
+----------------------+------------------------------------------+

Ids prefixed with ``_`` (e.g. ``_values-type``) are internal bridge validators
with ``sets=None`` — they are always active and cannot be disabled.

Validator naming convention
...........................

Validators are split into two flavors based on what they enforce:

* ``RfcValidator`` / ids ending in ``-rfc`` — enforce requirements that come
  directly from an RFC. Reasons reference specific RFC numbers.
* ``BpValidator`` / ids ending in ``-bp`` — enforce best-practice
  recommendations that aren't strictly required by an RFC (e.g. trailing
  ``.`` on hostnames).

Both follow the same config and registration paths described below; the
naming just makes the source of each rule explicit so you can opt in or
out with intent.

Opt-in RFC validators
.....................

Some stricter validators ship in the box but are not enabled by default,
typically because turning them on would break existing zones that don't
strictly conform. They follow the ``RfcValidator`` / ``-rfc`` naming
convention and are wired up the same way as any custom validator:

+--------------------+-----------------------------------------------------+
| id                 | description                                         |
+====================+=====================================================+
| ``srv-name-rfc``   | SRV name strict per RFC 2782 + RFC 6335 §5.1        |
+--------------------+-----------------------------------------------------+
| ``srv-value-rfc``  | SRV rdata strict per RFC 2782 (range, null target)  |
+--------------------+-----------------------------------------------------+

Example::

  validators:
    srv-name-rfc:
      class: octodns.record.srv.SrvNameRfcValidator
    srv-value-rfc:
      class: octodns.record.srv.SrvValueRfcValidator

  manager:
    validators:
      SRV:
        - srv-name-rfc
        - srv-value-rfc

Adding validators via config
............................

Custom validators are declared in a top-level ``validators:`` section (parallel
to ``providers:`` and ``processors:``)::

  validators:
    my-ttl-floor:
      class: mymodule.MinTtlValidator
      min_ttl: 300
      types:
        - MX

The ``class`` key specifies the dotted import path of a
:py:class:`~octodns.record.validator.RecordValidator` or
:py:class:`~octodns.record.validator.ValueValidator` subclass. The optional
``types`` key restricts the validator to those record types; omitting it
registers the validator for all types (``'*'``). All other keys are passed as
keyword arguments to ``__init__`` after the mandatory ``id`` (config key)
argument — including ``sets`` if set-based activation is desired.

Config-declared validators follow the same activation rules as built-in
validators: a validator with ``sets=None`` (the default) is always active; one
with an explicit ``sets`` value is activated when any of its sets appears in
``manager.enabled``. ``manager.validators`` can still be used to activate a
validator for additional record types beyond those listed under ``types``.

Disabling built-in validators
.............................

Individual built-in validators can be turned off under
``manager.disable_validators``::

  manager:
    disable_validators:
      '*':
        - healthcheck
      MX:
        - mx-value

``'*'`` removes the validator from every record type; a type string removes it
only for that type. Bridge validators (``_``-prefixed ids) cannot be disabled
and will raise a config error if listed here.

Attaching validators programmatically
......................................

Third-party modules (providers, processors, plugins) can register validators at
import time without any config entry. There are two paths depending on whether
the validator belongs to a ``Record`` subclass / value class or stands on its
own.

For a custom ``Record`` subclass (or a custom value class), declare a
``VALIDATORS`` class attribute. ``Record.register_type`` walks the new
class's MRO collecting every ``VALIDATORS`` list it finds, plus
``_value_type.VALIDATORS`` if defined, and registers each one against the
new type::

  from octodns.record import Record, ValuesMixin
  from octodns.record.validator import RecordValidator, ValueValidator

  class FooValueValidator(ValueValidator):
      def validate(self, value_cls, data, _type): ...

  class FooValue(str):
      VALIDATORS = [FooValueValidator('foo-value')]
      ...

  class NoPublicFooValidator(RecordValidator):
      def validate(self, record_cls, name, fqdn, data): ...

  class FooRecord(ValuesMixin, Record):
      _type = 'FOO'
      _value_type = FooValue
      VALIDATORS = [NoPublicFooValidator('no-public-foo')]

  Record.register_type(FooRecord)

To attach a validator to an already-registered record type, call
``Record.register_validator`` directly::

  from octodns.record import Record
  from octodns.record.validator import RecordValidator

  class NoPublicMxValidator(RecordValidator):
      def validate(self, record_cls, name, fqdn, data): ...

  Record.register_validator(NoPublicMxValidator('no-public-mx'), types=['MX'])

``types=None`` (the default) registers for all record types.

**Set membership and activation.** A validator's ``sets`` attribute controls
when it becomes active. The default is ``sets=None``, which means the
validator is always activated regardless of ``manager.enabled`` — the right
choice for most third-party validators that should always run. To opt a
validator into set-based filtering, pass an explicit ``sets`` at construction
time::

  Record.register_validator(
      StrictMxValidator('strict-mx', sets={'rfc'}), types=['MX']
  )

That validator is then only active when ``manager.enabled`` includes ``'rfc'``.
As long as the module is imported before Manager initialises, the validator
will be in the available registry and activated appropriately.

``strict_supports``
-------------------

``strict_supports`` is a ``Provider`` level parameter that comes into play when
a provider has been asked to create a record that it is unable to support. The
simplest case of this would be record type, e.g. ``SSHFP`` not being supported
by ``AzureProvider``. If such a record is passed to an ``AzureProvider`` as a
target the provider will take action based on the ``strict_supports``. When
``true`` it will throw an exception saying that it's unable to create the
record, when set to ``false`` it will log at ``WARNING`` with information about
what it's unable to do and how it is attempting to work around it. Other
examples of things that cannot be supported would be ``dynamic`` records on a
provider that only supports simple or the lack of support for specific geos in
a provider, e.g.  Route53Provider does not support ``NA-CA-*``.

It is worth noting that these errors will happen during the plan phase of
things so that problems will be visible without having to make changes.

As of octoDNS 1.x ``strict_supports`` is on by default. You have the choice to
set ``strict_supports=false`` on a per provider basis to request that things warn
and continue in a best-effort fashion.

Configuring ``strict_supports``
...............................

The ``strict_supports`` parameter is available on all providers and can be
configured in YAML as follows::

  providers:
    someprovider:
      class: whatever.TheProvider
      ...
      strict_supports: true

.. _automatic-ptr-generation:

Automatic PTR generation
------------------------

octoDNS supports automatically generating PTR records from the ``A``/``AAAA``
records it manages. For more information see the :doc:`auto_arpa`
documentation.

JSON Schema for zone YAML files
-------------------------------

octoDNS publishes a JSON Schema (Draft 2020-12) describing its zone YAML
file format. It is generated from the currently registered record types on
every docs build, so the schema matches the code in that release.

The schema is intended for editors and CI linters. octoDNS's own validation
is unchanged — it continues to handle error reporting with source context.

Available versions
..................

Read the Docs serves a copy of the schema under each version's ``_static``
directory:

- `Bundled with this documentation <_static/octodns.schema.json>`_ — always
  matches the version of octoDNS whose docs you are viewing
- `Latest release <https://octodns.readthedocs.io/en/stable/_static/octodns.schema.json>`_
  — recommended for most users; tracks the most recent release
- `Development <https://octodns.readthedocs.io/en/latest/_static/octodns.schema.json>`_
  — tracks ``main``
- A specific release, e.g.
  `v2.0.0 <https://octodns.readthedocs.io/en/v2.0.0/_static/octodns.schema.json>`_

Opting in with a modeline
.........................

The `yaml-language-server`_ (used by the ``redhat.vscode-yaml`` extension and
other editors) honors a modeline at the top of a YAML file:

.. code-block:: yaml

   # yaml-language-server: $schema=https://octodns.readthedocs.io/en/stable/_static/octodns.schema.json
   ---
   www:
     type: A
     ttl: 300
     value: 1.2.3.4

Editor configuration
....................

In VS Code (or any editor that uses ``yaml-language-server``) you can instead
associate the schema with a file pattern via ``yaml.schemas``::

  "yaml.schemas": {
    "https://octodns.readthedocs.io/en/stable/_static/octodns.schema.json": [
      "zones/*.yaml"
    ]
  }

Generating locally
..................

The ``octodns-schema`` CLI prints or writes the same schema:

.. code-block:: sh

   octodns-schema --output octodns.schema.json

.. _yaml-language-server: https://github.com/redhat-developer/yaml-language-server
