Records
=======

Underlying provider support for each of octoDNS's record types varies and some
providers have extra requirements or limitations. In cases where a record type
is not supported by a provider octoDNS will ignore it there and continue to
manage the record elsewhere. For example ``SSHFP`` is supported by Dyn, but not
Route53. If your source data includes an SSHFP record octoDNS will keep it in
sync on Dyn, but not consider it when evaluating the state of Route53. The best
way to find out what types are supported by a provider is to look for its
``supports`` method. If that method exists the logic will drive which records are
supported and which are ignored. If the provider does not implement the method
it will fall back to :py:attr:`BaseProvider.supports` which indicates full support.

Adding new record types to octoDNS is relatively straightforward, but will
require careful evaluation of each provider to determine whether or not it will
be supported and the addition of code in each to handle and test the new type.

Internal and RDATA formats
--------------------------

octoDNS uses two distinct text representations at its configuration/provider
boundary:

* **octoDNS internal format** is the data accepted from configuration and
  exposed by record and value objects. Text in this format is represented by
  Python Unicode strings and may use octoDNS-specific normalization. For
  example, TXT and SPF values internally escape semicolons.
* **RDATA presentation format** is the master-file-style text for the RDATA
  portion of one DNS resource record. Its quoting, escaping, field layout, and
  chunking follow the RFC for that record type.

RDATA presentation text is not a complete master-file record: it omits the
owner name, TTL, class, and record type. It is also not the binary octets used
by DNS wire format. For example, ``192.0.2.1`` is the RDATA presentation text
within the complete master-file record
``www.example.com. 300 IN A 192.0.2.1``.

Value conversion
................

Each RDATA value type provides ``to_rdata_text()`` and
``from_rdata_text()``. ``value.to_rdata_text()`` converts an octoDNS value
object to one Python ``str`` containing one RDATA value in presentation
format. ``ValueType.from_rdata_text(rdata)`` accepts one such ``str`` and
returns octoDNS internal data suitable for constructing that value type.
Invalid presentation text raises
:py:class:`octodns.record.rr.RdataParseError`, including TXT/SPF syntax and
UTF-8 decoding failures.

TXT and SPF need an additional compatibility rule because their legacy
``parse_rdata_text()`` method accepted raw internal text. When
``from_rdata_text()`` receives multiple wholly unquoted character-string
tokens, it treats the original input as raw text and preserves its spaces.
Quoted or mixed quoted/unquoted input follows DNS presentation semantics and
its character-strings concatenate. Providers that already know they have raw
TXT/SPF text should use ``TxtValue.normalize_raw_text()`` explicitly. The
method returns normalized internal text suitable for constructing either TXT
or SPF records.

Provider migration follows the input representation rather than a mechanical
method rename:

.. list-table:: Value parsing migration
   :header-rows: 1

   * - Existing input
     - Replacement
   * - Non-TXT/SPF ``ValueType.parse_rdata_text(rdata)``
     - ``ValueType.from_rdata_text(rdata)``
   * - Raw or unescaped TXT/SPF provider text
     - ``TxtValue.normalize_raw_text(value)``
   * - TXT/SPF RDATA presentation text
     - ``TxtValue.from_rdata_text(rdata)``

Generic processors and provider utilities should import
``value_to_rdata_text()`` and ``value_from_rdata_text()`` from
``octodns.record``. These public helpers select new or legacy value methods by
their defining position in the value type's MRO, allowing callers to support
third-party value types during the 1.x migration without implementing that
dispatch themselves.

New-style TXT/SPF values always render with the value-level conversion's
255-octet chunk limit. The record-level ``CHUNK_SIZE``, ``chunked_value()``,
``chunked_values``, and ``rr_values`` hooks are retained only for the
deprecated ``record.rrs`` path through octoDNS 1.x and will be removed in 2.0.
They do not customize ``to_rrset()`` for value types implementing the new
conversion API. The compatibility dispatcher may still consult ``rr_values``
when a third-party value type implements only the legacy ``rdata_text`` API.

Record conversion
.................

:py:meth:`octodns.record.base.Record.to_rrset` converts one octoDNS record to
one grouped :py:class:`octodns.record.rr.Rrset`. An ``Rrset`` has named
``name``, ``_type``, ``ttl``, and ``rdatas`` attributes. The owner name, type,
and TTL apply to every element of ``rdatas``, and each element must be a
Python ``str`` containing one RDATA value in presentation format. DNS class is
not stored; octoDNS assumes the Internet (``IN``) class. Construction rejects
a string or non-iterable ``rdatas`` container, an empty collection, and
non-string elements with
:py:class:`octodns.record.exception.RecordException`. ``Rrset`` objects
support equality and ordering across their name, type, TTL, and ordered RDATA
values.

:py:meth:`octodns.record.base.Record.from_rrset` performs the singular inverse
and returns one :py:class:`octodns.record.base.Record`.
:py:meth:`octodns.record.base.Record.from_rrsets` accepts an iterable of
grouped ``Rrset`` objects and returns multiple records. The bulk result is
ordered deterministically by owner name and type. An empty iterable returns an
empty list. Otherwise, bulk input may contain at most one ``Rrset`` for each
owner-name/type pair; duplicates raise
:py:class:`octodns.record.exception.RecordException`. An ``Rrset`` with no
RDATA values is also rejected with ``RecordException``. Single-value record
types, such as CNAME, require exactly one RDATA value. Unregistered record
types likewise raise ``RecordException`` rather than leaking ``KeyError``.

Both inverse methods pass ``lenient`` through record construction and attach
``source`` to every record they create. The deprecated compatibility entry
points propagate these arguments in the same way.

A provider reading RDATA presentation text can construct records as follows::

  from octodns.record import Record, Rrset

  rrset = Rrset(
      'www.example.com.',
      'A',
      300,
      ['192.0.2.1', '192.0.2.2'],
  )
  record = Record.from_rrset(
      zone,
      rrset,
      lenient=lenient,
      source=provider,
  )

A provider writing RDATA presentation text can consume the matching grouped
carrier::

  rrset = record.to_rrset()
  provider.write(
      name=rrset.name,
      record_type=rrset._type,
      ttl=rrset.ttl,
      rdatas=rrset.rdatas,
  )

Lenient Unicode TXT and SPF values
++++++++++++++++++++++++++++++++++

Valid TXT and SPF values use ASCII bytes and are split into chunks of at most
255 octets. When a non-ASCII internal value is deliberately accepted with
``lenient=True``, octoDNS preserves its historical character-based chunking
and quoting instead. This compatibility presentation text can be consumed by
``from_rdata_text()``, which decodes its character-string bytes as UTF-8 so
the Unicode internal value round-trips when every emitted character-string's
UTF-8 encoding fits within the DNS 255-octet limit. Longer values can retain a
historical character chunk whose UTF-8 encoding exceeds that limit; conforming
RDATA parsers reject such output. Arbitrary non-UTF-8 character-string bytes
are not supported because octoDNS's internal value contract is Unicode text.

Migrating from ``rrs``
......................

The deprecated ``record.rrs`` property remains available throughout octoDNS
1.x, but its plain tuple deliberately has a different positional order from
the named ``Rrset`` carrier::

  # Legacy tuple: (name, ttl, type, rdatas)
  name, ttl, record_type, rdatas = record.rrs

  # New carrier: Rrset(name, _type, ttl, rdatas)
  rrset = record.to_rrset()
  name = rrset.name
  record_type = rrset._type
  ttl = rrset.ttl
  rdatas = rrset.rdatas

Use named attributes on :py:class:`octodns.record.rr.Rrset`; do not apply the
legacy tuple's positional access pattern to it. The singular
:py:class:`octodns.record.rr.Rr` carrier and
:py:meth:`octodns.record.base.Record.from_rrs` are likewise compatibility APIs
scheduled for removal in octoDNS 2.0. Unlike the new RRset APIs,
``Record.from_rrs()`` retains its legacy behavior of using the first RDATA
value for a single-value record. The old
:py:class:`octodns.record.rr.RrParseError` name remains as an
identity-preserving compatibility alias for
:py:class:`octodns.record.rr.RdataParseError` throughout 1.x and will also be
removed in 2.0.

Advanced Record Support
-----------------------

* :doc:`dynamic_records` - the preferred method for configuring geo-location, weights, and healthcheck based fallback between pools of services.

Config (``YamlProvider``)
-------------------------

octoDNS records and :py:class:`octodns.provider.yaml.YamlProvider`'s schema is
essentially a 1:1 match. Properties on the objects will match keys in the
config.

Names
.....

Each top-level key in the yaml file is a record name. Two common special cases
are the root record ``''``, and a wildcard ``'*'``::

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

The above config lays out 4 records, ``A``s for ``example.com.``,
``www.example.com.``, and ``www.sub.example.com`` and a wildcard ``CNAME`` mapping
``*.example.com.`` to ``www.example.com.``.

Multiple records
................

In the above example each name had a single record, but there are cases where a
name will need to have multiple records associated with it. This can be
accomplished by using a list::

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

Record data
...........

Each record type has a corresponding set of required data. The easiest way to
determine what's required is probably to look at
:py:class:`octodns.record.Record`.  You may also utilize ``octodns-validate``
which will throw errors about what's missing when run.

``type`` is required for all records. ``ttl`` is optional. When TTL is not
specified the :py:class:`octodns.provider.yaml.YamlProvider`'s default will be
used. In any situation where an array of ``values`` can be used you can opt to
go with ``value`` as a single item if there's only one.

.. _lenience:

Lenience
........

octoDNS is fairly strict in terms of standards compliance and is opinionated in
terms of best practices. Examples of the former include SRV record naming
requirements and the latter that ALIAS records are constrained to the root of
zones. The strictness and support of providers varies so you may encounter
existing records that fail validation when you try to dump them or you may even
have use cases for which you need to create or preserve records that don't
validate. octoDNS's solution to this is the ``lenient`` flag.

It's best to think of the ``lenient`` flag as "I know what I'm doing and accept
any problems I run across." The main reason being is that some providers may
allow the non-compliant setup and others may not. The behavior of the
non-compliant records may even vary from one provider to another. Caveat
emptor.

Record priority for AutoArpa
++++++++++++++++++++++++++++

When multiple A or AAAA records point to the same IP, it is possible to set an
optional priority on each record. The records with the lowest priority will
have the highest preference when being processed by AutoArpa. The AutoArpa
provider will create PTR records in order of preference, up to a set limit
defined by the ``max_auto_arpa`` option in the provider configuration::

  test:
  - type: A
    value: 1.2.3.4
    octodns:
      auto_arpa_priority: 1

octodns-dump
++++++++++++

If you're trying to import a zone into octoDNS config file using
``octodns-dump``  which fails due to validation errors you can supply the
``--lenient`` argument to tell octoDNS that you acknowledge that things aren't
lining up with its expectations, but you'd like it to go ahead anyway. This
will do its best to populate the zone and dump the results out into an octoDNS
zone file and include the non-compliant bits. If you go to use that config file
octoDNS will again complain about the validation problems. You can correct them
in cases where that makes sense, but if you need to preserve the non-compliant
records read on for options.

Record level lenience
+++++++++++++++++++++

When there are non-compliant records configured in Yaml you can add the
following to tell octoDNS to do it's best to proceed with them anyway. If you
use ``--lenient`` above to dump a zone and you'd like to sync it as-is you can
mark the problematic records this way::

  'not-root':
    octodns:
      lenient: true
    type: ALIAS
    values: something.else.com.

Zone level lenience
+++++++++++++++++++

If you'd like to enable lenience for a whole zone you can do so with the
following, thought it's strongly encouraged to mark things at record level when
possible. The most common case where things may need to be done at the zone
level is when using something other than
:py:class:`octodns.provider.yaml.YamlProvider` as a source, e.g.  syncing from
``Route53Provider`` to ``Ns1Provider`` when there are non-compliant records in
the zone in Route53::

  non-compliant-zone.com.:
    lenient: true
    sources:
    - route53
    targets:
    - ns1

Restrict Record manipulations
+++++++++++++++++++++++++++++

octoDNS currently provides the ability to limit the number of updates/deletes
on DNS records by configuring a percentage of allowed operations as a provider
threshold.  If left unconfigured, suitable defaults take over instead. In the
below example, the Dyn provider is configured with limits of 40% on both update
and delete operations over all the records present::

  dyn:
      class: octodns.provider.dyn.DynProvider
      update_pcent_threshold: 0.4
      delete_pcent_threshold: 0.4

Additionally, thresholds can be configured at the zone level. Zone thresholds
take precedence over any provider default or explicit configuration. Zone
thresholds do not have a default::

  zones:
    example.com.:
      update_pcent_threshold: 0.2
      delete_pcent_threshold: 0.1

Provider specific record types
------------------------------

Creating and registering
........................

octoDNS has support for provider specific record types through a dynamic type
registration system. This functionality is powered by
py:meth:`octodns.record.Record.register_type` and can be used as follows::

  class _SpecificValue(object):
      ...

  class SomeProviderSpecificRecord(ValuesMixin, Record):
      _type = 'SomeProvider/SPECIFIC'
      _value_type = _SpecificValue

  Record.register_type(SomeProviderSpecificRecord)

Have a look at ``Route53Provider``'s `Route53Provider/ALIAS`_ for an example.

_`Route53Provider/ALIAS`: https://github.com/octodns/octodns-route53/blob/main/octodns_route53/record.py

In general this support is intended for record types that only make sense for a
single provider. If multiple providers have a similar record it may make sense
to implement it in octoDNS core.

Naming
......

By convention the record type should be prefixed with the provider class, e.g.
``Route53Provider`` followed by a ``/`` and an all-caps record type name
``ALIAS``, e.g. ``Route53Provider/ALIAS``.

YamlProvider support
....................

Once the type is registered :py:class:`octodns.provider.yaml.YamlProvider` will
automatically gain support for it and they can be included in your zone yaml
files::

  alias:
    type: Route53Provider/ALIAS
    values:
      - name: www
        type: A
      - name: www
        type: AAAA
