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
configured.

.. _Lenience: records.rst#lenience

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
