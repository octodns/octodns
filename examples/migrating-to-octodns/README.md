## Migrating to octoDNS via octodns-dump

Importing an existing DNS setup into octoDNS management is a very
straightforward process and can generally be completed in minutes.

Some relevant documentation for this example is in comments in the YAML configuration files.

* [config/octodns.yaml](config/octodns.yaml)
* [config/my-domain.com.yaml](config/my-domain.com.yaml)
* [config/unused-domain.io.yaml](config/unused-domain.io.yaml)

From here on this README focuses on the general process of running octoDNS to
create your initial config.

## Checking out the code and setting up the environment

You would not normally need to check out octoDNS itself, you instead would have
a git repo with only your configuration files. Here we're cloning the repo only
to get a copy of the example files.

```console
$ git clone https://github.com/octodns/octodns.git
$ cd octodns/examples/basic/
$ python3 -mvenv env
$ source env/bin/activate
(env) $ pip install -r requirements.txt
```

If you were instead creating a repo for your config from scratch it might look
something like:

```console
$ mkdir octodnsed
$ cd octodnsed
$ git init -b main
$ mkdir config
# Using your editor of choice create the main config file with your customized
# version of things, examples/basic/config/octodns.yaml is a good place to
# start.
$ vim config/octodns.yaml
# follow the process here and once complete
$ git add config
$ git commit -m "Importting existing records into octoDNS"
$ git push -u origin main
```

## Running octodns-dump

Once you have your configuration files and octoDNS installed you're ready to
dump your zone configs. Here we've assumed that the provider being used supports
`list_zones`, not all do. If you get an error to that effect see
[dynamic-zone-config](../dynamic-zone-config) for details on how to explicitly
list your zones in the config file.

The quoted * below is what tells octodns-dump to dynamically source the list of
zones and dump config files for all of them. If you would only like to dump a
specific zone you can replace it with the zone name, e.g. `my-domain.com.`,
making sure to include the trailing `.`


```console
(env) coho:migrating-to-octodns ross$ octodns-dump --config-file=config/octodns.yaml --output-dir config/  '*' some-provider
2023-08-25T10:36:00  [4413005312] INFO  Manager __init__: config_file=config/octodns.yaml, (octoDNS 1.0.0+6e7f036b)
2023-08-25T10:36:00  [4413005312] INFO  Manager _config_executor: max_workers=1
2023-08-25T10:36:00  [4413005312] INFO  Manager _config_include_meta: include_meta=False
2023-08-25T10:36:00  [4413005312] INFO  Manager _config_auto_arpa: auto_arpa=False
2023-08-25T10:36:00  [4413005312] INFO  Manager __init__: global_processors=[]
2023-08-25T10:36:00  [4413005312] INFO  Manager __init__: provider=config (octodns.provider.yaml 1.0.0+6e7f036b)
2023-08-25T10:36:00  [4413005312] INFO  Manager __init__: provider=some-provider (octodns.provider.yaml 1.0.0+6e7f036b)
2023-08-25T10:36:00  [4413005312] INFO  Manager dump: zone=*, output_dir=config/, output_provider=None, lenient=False, split=False, sources=['some-provider']
2023-08-25T10:36:00  [4413005312] INFO  Manager dump: using custom YamlProvider
2023-08-25T10:36:00  [4413005312] INFO  Manager sync:   dynamic zone=*, sources=[YamlProvider]
2023-08-25T10:36:00  [4413005312] INFO  Manager sync:      adding dynamic zone=my-domain.com.
2023-08-25T10:36:00  [4413005312] INFO  Manager sync:      adding dynamic zone=unused-domain.io.
Traceback (most recent call last):
  File "/Users/ross/octodns/octodns/examples/migrating-to-octodns/env/bin/octodns-dump", line 8, in <module>
    sys.exit(main())
             ^^^^^^
  File "/Users/ross/octodns/octodns/octodns/cmds/dump.py", line 51, in main
    manager.dump(
  File "/Users/ross/octodns/octodns/octodns/manager.py", line 868, in dump
    source.populate(zone, lenient=lenient)
  File "/Users/ross/octodns/octodns/octodns/provider/yaml.py", line 229, in populate
    self._populate_from_file(filename, zone, lenient)
  File "/Users/ross/octodns/octodns/octodns/provider/yaml.py", line 175, in _populate_from_file
    record = Record.new(
             ^^^^^^^^^^^
  File "/Users/ross/octodns/octodns/octodns/record/base.py", line 76, in new
    raise ValidationError(fqdn, reasons, context)
octodns.record.exception.ValidationError: Invalid record "my-domain.com.", ./target/my-domain.com.yaml, line 17, column 5
  - NS value "ns1.some-provider.com" missing trailing .
  - NS value "ns2.some-provider.com" missing trailing .
  - NS value "ns3.some-provider.com" missing trailing .
  - NS value "ns4.some-provider.com" missing trailing .
```

We've intentionally configured data in the provider without following
(octoDNS's) best practices as it's common to run across these sorts of things
when migrating. In this case the NS values are missing their trailing `.`,
`ns1.some-provider.com` should be `ns1.some-provider.com.`.

Regardless of whether or not you hit errors it is important to carefully look
over the output of octodns-dump to ensure that it was able to make sense of and
import everything it found. It usually can, but you may sometimes run across
things that it can't make sense of or otherwise doesn't support.

This is especially true if you have any advanced records configured in your
provider. octoDNS generally cannot convert records with functionality like
weights and/or geo-coding enabled. It'll generally import a "simple" version of
that record and indicate it's doing so with a WARNING log message. If you hit
this situation see [Dynamic Records](/docs/dynamic_records.md).

## Running octodns-dump again, now with --lenient

Back to our example, the missing `.`s aren't a huge deal and octoDNS can be
asked to ignore them with the `--lenient` argument.

```console
(env) coho:migrating-to-octodns ross$ octodns-dump --config-file=config/octodns.yaml --output-dir config/  '*' some-provider --lenient
2023-08-25T10:43:26  [4528057856] INFO  Manager __init__: config_file=config/octodns.yaml, (octoDNS 1.0.0+6e7f036b)
2023-08-25T10:43:26  [4528057856] INFO  Manager _config_executor: max_workers=1
2023-08-25T10:43:26  [4528057856] INFO  Manager _config_include_meta: include_meta=False
2023-08-25T10:43:26  [4528057856] INFO  Manager _config_auto_arpa: auto_arpa=False
2023-08-25T10:43:26  [4528057856] INFO  Manager __init__: global_processors=[]
2023-08-25T10:43:26  [4528057856] INFO  Manager __init__: provider=config (octodns.provider.yaml 1.0.0+6e7f036b)
2023-08-25T10:43:26  [4528057856] INFO  Manager __init__: provider=some-provider (octodns.provider.yaml 1.0.0+6e7f036b)
2023-08-25T10:43:26  [4528057856] INFO  Manager dump: zone=*, output_dir=config/, output_provider=None, lenient=True, split=False, sources=['some-provider']
2023-08-25T10:43:26  [4528057856] INFO  Manager dump: using custom YamlProvider
2023-08-25T10:43:26  [4528057856] INFO  Manager sync:   dynamic zone=*, sources=[YamlProvider]
2023-08-25T10:43:26  [4528057856] INFO  Manager sync:      adding dynamic zone=my-domain.com.
2023-08-25T10:43:26  [4528057856] INFO  Manager sync:      adding dynamic zone=unused-domain.io.
2023-08-25T10:43:26  [4528057856] WARNING Record Invalid record "my-domain.com.", ./target/my-domain.com.yaml, line 17, column 5
  - NS value "ns1.some-provider.com" missing trailing .
  - NS value "ns2.some-provider.com" missing trailing .
  - NS value "ns3.some-provider.com" missing trailing .
  - NS value "ns4.some-provider.com" missing trailing .
2023-08-25T10:43:26  [4528057856] INFO  YamlProvider[some-provider] populate:   found 10 records, exists=False
2023-08-25T10:43:26  [4528057856] INFO  YamlProvider[dump] plan: desired=my-domain.com.
2023-08-25T10:43:26  [4528057856] INFO  YamlProvider[dump] plan:   Creates=10, Updates=0, Deletes=0, Existing Records=0
2023-08-25T10:43:26  [4528057856] INFO  YamlProvider[dump] apply: making 10 changes to my-domain.com.
2023-08-25T10:43:26  [4528057856] INFO  YamlProvider[some-provider] populate:   found 0 records, exists=False
2023-08-25T10:43:26  [4528057856] INFO  YamlProvider[dump] plan: desired=unused-domain.io.
2023-08-25T10:43:26  [4528057856] WARNING YamlProvider[dump] root NS record supported, but no record is configured for unused-domain.io.
2023-08-25T10:43:26  [4528057856] INFO  YamlProvider[dump] plan:   No changes
2023-08-25T10:43:26  [4528057856] INFO  YamlProvider[dump] apply: making 0 changes to unused-domain.io.
```

## Examining the results

We can now take a look in the config/ directory to see the created zone files
along side our main config.

```console
(env) coho:migrating-to-octodns ross$ ls -1 config/
my-domain.com.yaml
octodns.yaml
unused-domain.io.yaml
```

If you open up the my-domain.com.yaml file you'll note that the root NS record values are missing
their trailing `.`s. octoDNS has done its best to dump things as they currently
are in the provider. That means that if you tried to generate a plan with
`octodns-sync` now it would fail b/c the configuration doesn't follow best
practices.

When migrating it's recommended to make as few changes to your config as
possible initially, that is you want to bring the setup as-is under octoDNS
management and avoid churn as much as possible. This is the safest approach,
change as little as possible and incrementally work towards having a fully
managed and compliant/best practice config.

So for now we'll enable `lenient` on the root NS record. For more details on
see the [lenience](../lenience/) example.

```yaml
...
  - octodns:
      lenient: true
    type: NS
    values:
    - ns1.some-provider.com
    - ns2.some-provider.com
    - ns3.some-provider.com
    - ns4.some-provider.com
...
```

## Generating our first plan

We can now ask octoDNS to create a plan to see if anything would change. Since
we've looked closely at the log output zone configuration files we have a pretty
good idea the answer is no.

```console
(env) coho:migrating-to-octodns ross$ octodns-sync --config-file=config/octodns.yaml
2023-08-25T11:07:44  [4644843008] INFO  Manager __init__: config_file=config/octodns.yaml, (octoDNS 1.0.0+6e7f036b)
2023-08-25T11:07:44  [4644843008] INFO  Manager _config_executor: max_workers=1
2023-08-25T11:07:44  [4644843008] INFO  Manager _config_include_meta: include_meta=False
2023-08-25T11:07:44  [4644843008] INFO  Manager _config_auto_arpa: auto_arpa=False
2023-08-25T11:07:44  [4644843008] INFO  Manager __init__: global_processors=[]
2023-08-25T11:07:44  [4644843008] INFO  Manager __init__: provider=config (octodns.provider.yaml 1.0.0+6e7f036b)
2023-08-25T11:07:44  [4644843008] INFO  Manager __init__: provider=some-provider (octodns.provider.yaml 1.0.0+6e7f036b)
2023-08-25T11:07:44  [4644843008] INFO  Manager sync: eligible_zones=[], eligible_targets=[], dry_run=True, force=False, plan_output_fh=<stdout>
2023-08-25T11:07:44  [4644843008] INFO  Manager sync:   sources=['config']
2023-08-25T11:07:44  [4644843008] INFO  Manager sync:   dynamic zone=*, sources=[YamlProvider]
2023-08-25T11:07:44  [4644843008] INFO  Manager sync:      adding dynamic zone=my-domain.com.
2023-08-25T11:07:44  [4644843008] INFO  Manager sync:      adding dynamic zone=unused-domain.io.
2023-08-25T11:07:44  [4644843008] INFO  Manager sync:   zone=my-domain.com.
2023-08-25T11:07:44  [4644843008] INFO  Manager sync:   sources=['config']
2023-08-25T11:07:44  [4644843008] INFO  Manager sync:   targets=['some-provider']
2023-08-25T11:07:44  [4644843008] INFO  Manager sync:   zone=unused-domain.io.
2023-08-25T11:07:44  [4644843008] INFO  Manager sync:   sources=['config']
2023-08-25T11:07:44  [4644843008] INFO  Manager sync:   targets=['some-provider']
2023-08-25T11:07:44  [4644843008] WARNING Record Invalid record "my-domain.com.", ./config/my-domain.com.yaml, line 9, column 5
  - NS value "ns1.some-provider.com" missing trailing .
  - NS value "ns2.some-provider.com" missing trailing .
  - NS value "ns3.some-provider.com" missing trailing .
  - NS value "ns4.some-provider.com" missing trailing .
2023-08-25T11:07:44  [4644843008] INFO  YamlProvider[config] populate:   found 10 records, exists=False
2023-08-25T11:07:44  [4644843008] INFO  YamlProvider[some-provider] plan: desired=my-domain.com.
2023-08-25T11:07:44  [4644843008] WARNING Record Invalid record "my-domain.com.", ./target/my-domain.com.yaml, line 17, column 5
  - NS value "ns1.some-provider.com" missing trailing .
  - NS value "ns2.some-provider.com" missing trailing .
  - NS value "ns3.some-provider.com" missing trailing .
  - NS value "ns4.some-provider.com" missing trailing .
2023-08-25T11:07:44  [4644843008] INFO  YamlProvider[some-provider] populate:   found 10 records, exists=False
2023-08-25T11:07:44  [4644843008] INFO  YamlProvider[some-provider] plan:   No changes
2023-08-25T11:07:44  [4644843008] INFO  YamlProvider[config] populate:   found 0 records, exists=False
2023-08-25T11:07:44  [4644843008] INFO  YamlProvider[some-provider] plan: desired=unused-domain.io.
2023-08-25T11:07:44  [4644843008] INFO  YamlProvider[some-provider] populate:   found 0 records, exists=False
2023-08-25T11:07:44  [4644843008] WARNING YamlProvider[some-provider] root NS record supported, but no record is configured for unused-domain.io.
2023-08-25T11:07:44  [4644843008] INFO  YamlProvider[some-provider] plan:   No changes
2023-08-25T11:07:44  [4644843008] INFO  Plan
********************************************************************************
No changes were planned
********************************************************************************
```

If you had unsupported record types or advanced features in use this may not be
the case. It's completely safe to generate a plan, octoDNS won't make any
changes.

If you see things in the plan output section it's time to triple check and make
sure they're, hopefully minimal, modifications your OK with making.

If the changes are due to advanced functionality you'll need to step back and
plan a careful migration over to [Dynamic Records](/docs/dynamic_records.md)
which is beyond the scope of this example.

## What's Next

So now you can commit your config and start managing you DNS with octoDNS rather
than clicking buttons in UIs or using whatever you previous had used.

* Check out [octoDNS basic example](../basic) for an example of how to create zone configuration YAML files from your existing provider's configuration
* Have a look at [managing SPF values](../managing-spf) for details on the best practices for configuring email related DNS records with octoDNS
* For a complete list check out the [Examples Directory](../)
