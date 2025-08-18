Writing a Custom Source
=======================

Introduction
------------

Creating a custom source of record data for octoDNS is pretty simple and
involves a bit of boilerplate and then filling in a single method,
:py:meth:`octodns.source.base.BaseSource.populate`, with any logic required
to fetch or create the desired records. In this example records will be created
for the first 25 elements of the `Fibonacci Sequence`_. While contrived it
should illustrate the process and requirements.

.. _Fibonacci Sequence: https://en.wikipedia.org/wiki/Fibonacci_sequence

Some relevant documentation for this example is in comments in the YAML
configuration files and python code.

* :download:`config/octodns.yaml`
* :download:`config/dns.math.yaml`
* :download:`fibonacci.py`

From here on this README focuses on the custom source and the process of
running octoDNS with access to it.

Checking out the code and setting up the environment
----------------------------------------------------

You would not normally need to check out octoDNS itself, you instead would have
a git repo with only your configuration files. Here we're cloning the repo only
to get a copy of the example files::

  $ git clone https://github.com/octodns/octodns.git
  $ cd octodns/examples/basic/
  $ python3 -mvenv env
  $ source ../env.sh
  $ source env/bin/activate
  (env) $ pip install -r requirements.txt

Finally check out :ref:`Running PowerDNS` to get a local instance of PowerDNS
up and going before continuing.

Running octoDNS sync
--------------------

Once you have your custom source, configuration files, and octoDNS installed
you're ready to run the sync command to get it to plan an initial set of
changes. The main difference here compared to the :ref:`basic-setup` is setting
``PYTHONPATH`` so the source file can be located::

  (env) $ export PYTHONPATH=.
  (env) $ octodns-sync --config-file config/octodns.yaml
  2025-08-17T17:14:58  [140224800168896] INFO  Manager __init__: config_file=config/octodns.yaml, (octoDNS 1.13.0)
  2025-08-17T17:14:58  [140224800168896] INFO  Manager _config_executor: max_workers=1
  2025-08-17T17:14:58  [140224800168896] INFO  Manager _config_include_meta: include_meta=False
  2025-08-17T17:14:58  [140224800168896] INFO  Manager _config_enable_checksum: enable_checksum=False
  2025-08-17T17:14:58  [140224800168896] INFO  Manager _config_auto_arpa: auto_arpa=False
  2025-08-17T17:14:58  [140224800168896] INFO  Manager __init__: global_processors=[]
  2025-08-17T17:14:58  [140224800168896] INFO  Manager __init__: global_post_processors=[]
  2025-08-17T17:14:58  [140224800168896] INFO  Manager __init__: provider=config (octodns.provider.yaml 1.13.0)
  2025-08-17T17:14:58  [140224800168896] INFO  Manager __init__: provider=powerdns (octodns_powerdns 1.0.0)
  2025-08-17T17:14:58  [140224800168896] INFO  Manager __init__: provider=fibonacci (fibonacci n/a)
  2025-08-17T17:14:58  [140224800168896] INFO  Manager sync: eligible_zones=[], eligible_targets=[], dry_run=True, force=False, plan_output_fh=<stdout>, checksum=None
  2025-08-17T17:14:58  [140224800168896] INFO  Manager sync:   zone=dns.math.
  2025-08-17T17:14:58  [140224800168896] INFO  Manager sync:     sources=['config', 'fibonacci']
  2025-08-17T17:14:58  [140224800168896] INFO  Manager sync:     processors=[]
  2025-08-17T17:14:58  [140224800168896] INFO  Manager sync:     targets=['powerdns']
  2025-08-17T17:14:58  [140224800168896] INFO  YamlProvider[config] populate:   found 1 records, exists=True
  2025-08-17T17:14:58  [140224800168896] INFO  FibonacciProvider[fibonacci] populate:   found 25 records, exists=False
  2025-08-17T17:14:58  [140224800168896] INFO  PowerDnsProvider[powerdns] plan: desired=dns.math.
  2025-08-17T17:14:58  [140224800168896] INFO  PowerDnsProvider[powerdns] populate:   found 1 records, exists=True
  2025-08-17T17:14:58  [140224800168896] WARNING PowerDnsProvider[powerdns] root NS record supported, but no record is configured for dns.math.
  2025-08-17T17:14:58  [140224800168896] INFO  PowerDnsProvider[powerdns] plan:   Creates=25, Updates=0, Deletes=0, Existing=1, Meta=False
  2025-08-17T17:14:58  [140224800168896] INFO  Plan
  ********************************************************************************
  * dns.math.
  ********************************************************************************
  * powerdns (PowerDnsProvider)
  *   Create <TxtRecord TXT 3600, fibonacci-0.dns.math., ['0']> ()
  *   Create <TxtRecord TXT 3600, fibonacci-1.dns.math., ['1']> ()
  *   Create <TxtRecord TXT 3600, fibonacci-10.dns.math., ['55']> ()
  *   Create <TxtRecord TXT 3600, fibonacci-11.dns.math., ['89']> ()
  *   Create <TxtRecord TXT 3600, fibonacci-12.dns.math., ['144']> ()
  *   Create <TxtRecord TXT 3600, fibonacci-13.dns.math., ['233']> ()
  *   Create <TxtRecord TXT 3600, fibonacci-14.dns.math., ['377']> ()
  *   Create <TxtRecord TXT 3600, fibonacci-15.dns.math., ['610']> ()
  *   Create <TxtRecord TXT 3600, fibonacci-16.dns.math., ['987']> ()
  *   Create <TxtRecord TXT 3600, fibonacci-17.dns.math., ['1597']> ()
  *   Create <TxtRecord TXT 3600, fibonacci-18.dns.math., ['2584']> ()
  *   Create <TxtRecord TXT 3600, fibonacci-19.dns.math., ['4181']> ()
  *   Create <TxtRecord TXT 3600, fibonacci-2.dns.math., ['1']> ()
  *   Create <TxtRecord TXT 3600, fibonacci-20.dns.math., ['6765']> ()
  *   Create <TxtRecord TXT 3600, fibonacci-21.dns.math., ['10946']> ()
  *   Create <TxtRecord TXT 3600, fibonacci-22.dns.math., ['17711']> ()
  *   Create <TxtRecord TXT 3600, fibonacci-23.dns.math., ['28657']> ()
  *   Create <TxtRecord TXT 3600, fibonacci-24.dns.math., ['46368']> ()
  *   Create <TxtRecord TXT 3600, fibonacci-3.dns.math., ['2']> ()
  *   Create <TxtRecord TXT 3600, fibonacci-4.dns.math., ['3']> ()
  *   Create <TxtRecord TXT 3600, fibonacci-5.dns.math., ['5']> ()
  *   Create <TxtRecord TXT 3600, fibonacci-6.dns.math., ['8']> ()
  *   Create <TxtRecord TXT 3600, fibonacci-7.dns.math., ['13']> ()
  *   Create <TxtRecord TXT 3600, fibonacci-8.dns.math., ['21']> ()
  *   Create <TxtRecord TXT 3600, fibonacci-9.dns.math., ['34']> ()
  *   Summary: Creates=25, Updates=0, Deletes=0, Existing=1, Meta=False
  ********************************************************************************

The log output
..............

Everything here matches the output and meaning of the first run in
:ref:`basic-setup`, with the important difference that both the statically
configured and dynamically generated records are listed as planned changes.
From here a ``--doit`` run can be executed to create the records in the
PowerDNS server, which can then be queried::

Viewing the results
-------------------

``dig`` can now be run to query for the records::

  $ dig +short TXT dns.math.
  "Try querying for TXT records named fibonacci-N where N is an integer 0-25"
  $ dig +short TXT fibonacci-0.dns.math.
  "0"
  $ dig +short TXT fibonacci-23.dns.math.
  "28657"
  $ dig +short TXT fibonacci-99.dns.math.

Next Steps
----------

If the source will only be used in a single octoDNS setup and you're OK with it
living alongside your config, as was done in this example the
:download:`fibonacci.py` file can be used as a starting point. It is also
possible to create custom processors and providers that work in the same
manner, though the details of the code involved are outside the scope of this
example.

If the provider will be used more widely or published for others to use, see
`octodns-template`_.

.. _octodns-template: https://github.com/octodns/octodns-template
