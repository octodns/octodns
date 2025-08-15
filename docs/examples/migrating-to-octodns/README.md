# Migrating to octoDNS

Importing an existing DNS setup into octoDNS management is a very
straightforward process and can generally be completed in minutes.

Some relevant documentation for this example is in comments in the YAML
configuration files.

* [config/octodns.yaml](config/octodns.yaml)
* [populate/octodns.yaml](populate/octodns.yaml)
* [populate/my-dumpable.com.yaml](populate/my-dumpable.com.yaml)
* [populate/unused-dumpable.com.yaml](populate/unused-dumpable.com.yaml)

From here on this README focuses on the process of using `octodns-dump` to
import your existing DNS data into octoDNS.

## Checking out the code and setting up the environment

You would not normally need to check out octoDNS itself, you instead would have
a git repo with only your configuration files. Here we're cloning the repo only
to get a copy of the example files.

```console
$ git clone https://github.com/octodns/octodns.git
$ cd octodns/examples/basic/
$ python3 -mvenv env
$ source ../env.sh
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

## Populating some data that we can later dump

We need zone & record data in our provider in order to have something to dump
out into a YAML config, thus our first step is to populate PowerDNS. This is
just to have something to work with the the actual process that begins in the
next step. It's not something you'd normally do when migrating to octoDNS.

Step 0 is to get a local PowerDNS instance running.
Check out out [Running PowerDNS](#running-powerdns) for info on
starting that up. Once you've done that run the following. You can ignore the
output and move on to the next step.

```console
(env) $ octodns-sync --config-file=populate/octodns.yaml --doit
```

## Running octodns-dump

Once you have your configuration files and octoDNS installed you're ready to
dump your zone configs. Here we've assumed that the provider being used
supports `list_zones`, not all do. If you get an error to that effect see
[dynamic-zone-config](#dynamic-zone-config) for
details on how to explicitly list your zones in the config file.

We first tell octodns-dump where to find our config file. We then tell it that
we want to use the output provider defined in that file named `config` rather
than having a default one auto-created. This would allow us to customize the
details of the provider, e.g. things like the `default_ttl`.

We'll then tell dump where we would like it to write our zone files, in this
case we want it to put them into `config` provider's directory `./config`.

The quoted * tells octodns-dump to dynamically source the list of zones and
dump config files for all of them. If you would only like to dump a specific
zone you can replace it with the zone name, e.g. `my-domain.com.`, making sure
to include the trailing `.`

The final argument passed to `octodns-dump` is the source of data you'd like to
dump. Here that's our existing provider `powerdns`.

Note that if you're previously run other examples you may see entries in the
log output for those zones in addition to the ones we populated for this
exercise. They shouldn't cause any problems and can be ignored.

```console
(env) $ octodns-dump --config-file=config/octodns.yaml --output-provider config --output-dir ./config '*' powerdns
2023-09-12T09:39:59  [4580544000] INFO  Manager __init__: config_file=config/octodns.yaml, (octoDNS 1.0.0+bca53089)
2023-09-12T09:39:59  [4580544000] INFO  Manager _config_executor: max_workers=1
2023-09-12T09:39:59  [4580544000] INFO  Manager _config_include_meta: include_meta=False
2023-09-12T09:39:59  [4580544000] INFO  Manager _config_auto_arpa: auto_arpa=False
2023-09-12T09:39:59  [4580544000] INFO  Manager __init__: global_processors=[]
2023-09-12T09:39:59  [4580544000] INFO  Manager __init__: provider=config (octodns.provider.yaml 1.0.0+bca53089)
2023-09-12T09:40:00  [4580544000] INFO  Manager __init__: provider=powerdns (octodns_powerdns 0.0.4+3189e9c2)
2023-09-12T09:40:00  [4580544000] INFO  Manager dump: zone=*, output_dir=./config, output_provider=config, lenient=False, split=False, sources=['powerdns']
2023-09-12T09:40:00  [4580544000] INFO  Manager dump: using specified output_provider=config
2023-09-12T09:40:00  [4580544000] INFO  Manager sync:   dynamic zone=*, sources=[PowerDnsProvider]
2023-09-12T09:40:00  [4580544000] INFO  Manager sync:      adding dynamic zone=my-dumpable.com.
2023-09-12T09:40:00  [4580544000] INFO  Manager sync:      adding dynamic zone=unused-domain.io.
Traceback (most recent call last):
  File "/Users/ross/octodns/octodns/examples/migrating-to-octodns/env/bin/octodns-dump", line 8, in <module>
    sys.exit(main())
             ^^^^^^
  File "/Users/ross/octodns/octodns/examples/migrating-to-octodns/env/lib/python3.11/site-packages/octodns/cmds/dump.py", line 51, in main
    manager.dump(
  File "/Users/ross/octodns/octodns/examples/migrating-to-octodns/env/lib/python3.11/site-packages/octodns/manager.py", line 868, in dump
    source.populate(zone, lenient=lenient)
  File "/Users/ross/octodns/octodns/examples/migrating-to-octodns/env/lib/python3.11/site-packages/octodns_powerdns/__init__.py", line 433, in populate
    record = Record.new(
             ^^^^^^^^^^^
  File "/Users/ross/octodns/octodns/examples/migrating-to-octodns/env/lib/python3.11/site-packages/octodns/record/base.py", line 76, in new
    raise ValidationError(fqdn, reasons, context)
octodns.record.exception.ValidationError: Invalid record "sshfp.my-dumpable.com."
  - unrecognized algorithm "42"
  - unrecognized algorithm "43"
```

We've intentionally configured data in the provider without following
(octoDNS's) best practices as it's common to run across these sorts of things
when migrating. In this case there is a SSHFP record with invalid `algorithm`s.

Regardless of whether or not you hit errors it is important to carefully look
over the output of octodns-dump to ensure that it was able to make sense of and
import everything it found. It usually can, but you may sometimes run across
things that it can't make sense of or otherwise doesn't support.

This is especially true if you have any advanced records configured in your
provider. octoDNS generally cannot convert records with functionality like
weights and/or geo-coding enabled. It'll generally import a "simple" version of
that record and indicate it's doing so with a WARNING log message. If you hit
this situation see [Dynamic Records](/dynamic_records.rst).

## Running octodns-dump again, now with --lenient

Back to our example, the invalid `algorithm`s aren't a huge deal and octoDNS
can be asked to ignore them with the `--lenient` argument.

```console
(env) $ octodns-dump --config-file=config/octodns.yaml --output-provider config --output-dir ./config '*' powerdns --lenient
2023-09-12T09:47:48  [4566433280] INFO  Manager __init__: config_file=config/octodns.yaml, (octoDNS 1.0.0+bca53089)
2023-09-12T09:47:48  [4566433280] INFO  Manager _config_executor: max_workers=1
2023-09-12T09:47:48  [4566433280] INFO  Manager _config_include_meta: include_meta=False
2023-09-12T09:47:48  [4566433280] INFO  Manager _config_auto_arpa: auto_arpa=False
2023-09-12T09:47:48  [4566433280] INFO  Manager __init__: global_processors=[]
2023-09-12T09:47:48  [4566433280] INFO  Manager __init__: provider=config (octodns.provider.yaml 1.0.0+bca53089)
2023-09-12T09:47:48  [4566433280] INFO  Manager __init__: provider=powerdns (octodns_powerdns 0.0.4+3189e9c2)
2023-09-12T09:47:48  [4566433280] INFO  Manager dump: zone=*, output_dir=./config, output_provider=config, lenient=True, split=False, sources=['powerdns']
2023-09-12T09:47:48  [4566433280] INFO  Manager dump: using specified output_provider=config
2023-09-12T09:47:48  [4566433280] INFO  Manager sync:   dynamic zone=*, sources=[PowerDnsProvider]
2023-09-12T09:47:48  [4566433280] INFO  Manager sync:      adding dynamic zone=my-dumpable.com.
2023-09-12T09:47:48  [4566433280] INFO  Manager sync:      adding dynamic zone=unused-dumpable.com.
2023-09-12T09:47:48  [4566433280] WARNING Record Invalid record "sshfp.my-dumpable.com."
  - unrecognized algorithm "42"
  - unrecognized algorithm "43"
2023-09-12T09:47:48  [4566433280] INFO  PowerDnsProvider[powerdns] populate:   found 8 records, exists=True
2023-09-12T09:47:48  [4566433280] INFO  YamlProvider[config] plan: desired=my-dumpable.com.
2023-09-12T09:47:48  [4566433280] INFO  YamlProvider[config] plan:   Creates=8, Updates=0, Deletes=0, Existing Records=0
2023-09-12T09:47:48  [4566433280] INFO  YamlProvider[config] apply: making 8 changes to my-dumpable.com.
2023-09-12T09:47:48  [4566433280] INFO  PowerDnsProvider[powerdns] populate:   found 1 records, exists=True
2023-09-12T09:47:49  [4566433280] INFO  YamlProvider[config] plan: desired=unused-dumpable.com.
2023-09-12T09:47:49  [4566433280] WARNING YamlProvider[config] root NS record supported, but no record is configured for unused-dumpable.com.
2023-09-12T09:47:49  [4566433280] INFO  YamlProvider[config] plan:   Creates=1, Updates=0, Deletes=0, Existing Records=0
2023-09-12T09:47:49  [4566433280] INFO  YamlProvider[config] apply: making 1 changes to unused-dumpable.com.
```

With `--lenient` we now see a warning about the validation problems, but
octoDNS does its best to continue anyway.

## Examining the results

We can now take a look in the config/ directory to see the created zone files
along side our main config.

```console
(env) ls -1 config/
my-dumpable.com.yaml
octodns.yaml
unused-dumpable.com.yaml
```

Again note if you're run through other examples you may see more files for
their zones in this directory. They can be ignored for the purpose of the
example, but they will be imported and managed nonetheless.

If you open up the my-dumpable.com.yaml file you'll note that the SSHFP
record's values have 42 and 43 for their algorithm field.

With those values if you tried to generate a plan with `octodns-sync` now it
would fail with validation errors.

When migrating it's recommended to make as few changes to your config as
possible initially, that is you want to bring the setup as-is under octoDNS
management. This is the safest approach, change as little as possible and
incrementally work towards having a fully managed and compliant/best practice
config.

So for now we'll enable `lenient` on the SSHFP record by editing
my-dumpable.com.yaml adding `octodns.lenient = true` as shown below. For more
details on see [lenience](#lenience).

```yaml
...
sshpf:
  # TODO: look into bringing this record into compliance
  octodns:
    lenient: true
  type: SSHFP
  values:
  - algorithm: 42
    fingerprint: abcdef1234567890
    fingerprint_type: 1
  - algorithm: 43
    fingerprint: abcdef1234567890
    fingerprint_type: 1
...
```

## Generating our first plan

We can now ask octoDNS to create a plan to see if anything would change. Since
we've looked closely at the log output zone configuration files we have a pretty
good idea the answer is no.

```console
(env) $ octodns-sync --config-file=config/octodns.yaml
...
2023-09-12T10:04:27  [4608876032] INFO  PowerDnsProvider[powerdns] plan: desired=unused-dumpable.com.
2023-09-12T10:04:27  [4608876032] INFO  PowerDnsProvider[powerdns] populate:   found 1 records, exists=True
2023-09-12T10:04:27  [4608876032] WARNING PowerDnsProvider[powerdns] root NS record supported, but no record is configured for unused-dumpable.com.
2023-09-12T10:04:27  [4608876032] INFO  PowerDnsProvider[powerdns] plan:   No changes
2023-09-12T10:04:27  [4608876032] INFO  YamlProvider[config] populate:   found 5 records, exists=False
2023-09-12T10:04:27  [4608876032] INFO  PowerDnsProvider[powerdns] plan: desired=exxampled.com.
2023-09-12T10:04:27  [4608876032] INFO  PowerDnsProvider[powerdns] populate:   found 5 records, exists=True
2023-09-12T10:04:27  [4608876032] INFO  PowerDnsProvider[powerdns] plan:   No changes
2023-09-12T10:04:27  [4608876032] INFO  Plan
********************************************************************************
No changes were planned
********************************************************************************
```

Most of the output above is omitted, this is the final few lines showing that
no changes need to be made to get `powerdns` to match `config`. It does have a
warning about the lack of root NS records in `unused-dumpable.com.`, but we'll
ignore that in this example.

If you had unsupported record types or advanced features in use this may not be
the case and you may see changes. It's completely safe to generate a plan,
octoDNS won't make any of the changes listed.

If you see things in the plan output section it's time to triple check and make
sure they're, hopefully minimal, modifications your OK with making.

If the changes are due to advanced functionality you'll need to step back and
plan a careful migration over to [Dynamic Records](/dynamic_records.rst)
which is beyond the scope of this example.

## What's Next

So now you can commit your config and start managing you DNS with octoDNS rather
than clicking buttons in UIs or using whatever you previous had used.

* Check out [octoDNS basic example](../basic/README.md) for an example of how to create zone configuration YAML files from your existing provider's configuration
* For a complete list check out the [Examples Directory](../README.rst)
