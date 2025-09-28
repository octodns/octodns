(basic-setup)=

# Basic Setup

This is the starting point octoDNS config, it's pretty similar to what you
might see for managing a set of personal domains or a small business.

Most of the actual documentation for this example is found in the comments in
the YAML configuration files.

* [config/octodns.yaml](config/octodns.yaml)
* [config/my-domain.com.yaml](config/my-domain.com.yaml)
* [config/unused-domain.io.yaml](config/unused-domain.io.yaml)

From here on this README focuses on the general process of running octoDNS.

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

Finally check out [Running PowerDNS](#running-powerdns) to get a local
instance of PowerDNS up and going before continuing.

## Running octoDNS the first time

Once you have your configuration files and octoDNS installed you're ready to
run the sync command to get it to plan an initial set of changes.

```console
(env) $ octodns-sync --config-file=config/octodns.yaml
2023-08-23T15:09:51  [4577488384] INFO  Manager __init__: config_file=config/octodns.yaml, (octoDNS 1.0.1)
2023-08-23T15:09:51  [4577488384] INFO  Manager _config_executor: max_workers=1
2023-08-23T15:09:51  [4577488384] INFO  Manager _config_include_meta: include_meta=False
2023-08-23T15:09:51  [4577488384] INFO  Manager _config_auto_arpa: auto_arpa=False
2023-08-23T15:09:51  [4577488384] INFO  Manager __init__: global_processors=[]
2023-08-23T15:09:51  [4577488384] INFO  Manager __init__: provider=config (octodns.provider.yaml 1.0.1)
2023-08-23T15:09:51  [4577488384] INFO  SpfSource[no-mail] __init__: id=no-mail, a_records=[], mx_records=[], ip4_addresses=[], ip6_addresses=[], includes=[], exists=[], soft_fail=False, merging_enabled=False, ttl=3600
2023-08-23T15:09:51  [4577488384] INFO  Manager __init__: provider=no-mail (octodns_spf 0.0.2)
2023-08-23T15:09:51  [4577488384] INFO  Manager __init__: provider=yaml (octodns.provider.yaml 1.0.1)
2023-08-23T15:09:51  [4577488384] INFO  Manager sync: eligible_zones=[], eligible_targets=[], dry_run=True, force=False, plan_output_fh=<stdout>
2023-08-23T15:09:51  [4577488384] INFO  Manager sync:   sources=['config', 'no-mail']
2023-08-23T15:09:51  [4577488384] INFO  Manager sync:   dynamic zone=*, sources=[YamlProvider, SpfSource]
2023-08-23T15:09:51  [4577488384] INFO  Manager sync:      adding dynamic zone=my-domain.com.
2023-08-23T15:09:51  [4577488384] INFO  Manager sync:      adding dynamic zone=unused-domain.io.
2023-08-23T15:09:51  [4577488384] INFO  Manager sync:   zone=my-domain.com.
2023-08-23T15:09:51  [4577488384] INFO  Manager sync:   sources=['config', 'no-mail']
2023-08-23T15:09:51  [4577488384] INFO  Manager sync:   targets=['yaml']
2023-08-23T15:09:51  [4577488384] INFO  Manager sync:   zone=unused-domain.io.
2023-08-23T15:09:51  [4577488384] INFO  Manager sync:   sources=['config', 'no-mail']
2023-08-23T15:09:51  [4577488384] INFO  Manager sync:   targets=['yaml']
2023-08-23T15:09:51  [4577488384] INFO  YamlProvider[config] populate:   found 9 records, exists=False
2023-08-23T15:09:51  [4577488384] INFO  SpfSource[no-mail] populate:   found 0 records, exists=False
2023-08-23T15:09:51  [4577488384] INFO  PowerDnsProvider[powerdns] plan: desired=my-domain.com.
2023-08-23T15:09:51  [4577488384] WARNING PowerDnsProvider[powerdns] root NS record supported, but no record is configured for my-domain.com.
2023-08-23T15:09:51  [4577488384] INFO  PowerDnsProvider[powerdns] plan:   Creates=9, Updates=0, Deletes=0, Existing Records=0
2023-08-23T15:09:51  [4577488384] INFO  YamlProvider[config] populate:   found 0 records, exists=False
2023-08-23T15:09:51  [4577488384] INFO  SpfSource[no-mail] populate:   found 1 records, exists=False
2023-08-23T15:09:51  [4577488384] INFO  PowerDnsProvider[powerdns] plan: desired=unused-domain.io.
2023-08-23T15:09:51  [4577488384] WARNING PowerDnsProvider[powerdns] root NS record supported, but no record is configured for unused-domain.io.
2023-08-23T15:09:51  [4577488384] INFO  PowerDnsProvider[powerdns] plan:   Creates=1, Updates=0, Deletes=0, Existing Records=0
2023-08-23T15:09:51  [4577488384] INFO  Plan
********************************************************************************
* unused-domain.io.
********************************************************************************
* powerdns (PowerDnsProvider)
*   Create Zone<unused-domain.io.>
*   Create <TxtRecord TXT 3600, unused-domain.io., ['v=spf1 -all']> ()
*   Summary: Creates=1, Updates=0, Deletes=0, Existing Records=0
********************************************************************************
* my-domain.com.
********************************************************************************
* powerdns (PowerDnsProvider)
*   Create Zone<my-domain.com.>
*   Create <ARecord A 3600, my-domain.com., ['203.0.113.42', '203.0.113.43']> (config)
*   Create <AaaaRecord AAAA 3600, my-domain.com., ['2001:db8::44']> (config)
*   Create <TxtRecord TXT 3600, my-domain.com., ['some-verification=3becb991-932f-4433-a280-9df6f39b6194', 'v=spf1 -all', 'z-other-thing=this proves i have control over this domain']> (config)
*   Create <ARecord A 3600, *.my-domain.com., ['203.0.113.45']> (config)
*   Create <AaaaRecord AAAA 3600, *.my-domain.com., ['2001:db8::46']> (config)
*   Create <TxtRecord TXT 3600, nadcbiqkbgq._companyname.my-domain.com., ['a-different-proof-of-ownership']> (config)
*   Create <CnameRecord CNAME 3600, pointer.my-domain.com., look.over-here.net.> (config)
*   Create <ARecord A 3600, www.my-domain.com., ['203.0.113.42', '203.0.113.43']> (config)
*   Create <AaaaRecord AAAA 3600, www.my-domain.com., ['2001:db8::44']> (config)
*   Summary: Creates=9, Updates=0, Deletes=0, Existing Records=0
********************************************************************************
```

### The log output

It's always a good idea to scan over the logging output of an octoDNS run. Most
of it is informational, telling you what has been configured and providing a
big picture idea of what's happening while planning. You will sometimes see
WARNINGS, these are generally telling you that there's something you should
think about or look into.

In the run above there was a warning about root/APEX NS records being supported
by the provider, YamlProvider, and not present in the config. Not all providers
support managing the root NS records, some just hard code their own name
servers.

```console
2023-08-23T15:09:51  [4577488384] WARNING PowerDnsProvider[powerdns] root NS record supported, but no record is configured for my-domain.com.
```

### The plan output

```console
********************************************************************************
* unused-domain.io.
********************************************************************************
* powerdns (PowerDnsProvider)
*   Create Zone<unused-domain.io.>
*   Create <TxtRecord TXT 3600, unused-domain.io., ['v=spf1 -all']> ()
*   Summary: Creates=1, Updates=0, Deletes=0, Existing Records=0
********************************************************************************
* my-domain.com.
********************************************************************************
* powerdns (PowerDnsProvider)
*   Create Zone<my-domain.com.>
*   Create <ARecord A 3600, my-domain.com., ['203.0.113.42', '203.0.113.43']> (config)
*   Create <AaaaRecord AAAA 3600, my-domain.com., ['2001:db8::44']> (config)
*   Create <TxtRecord TXT 3600, my-domain.com., ['some-verification=3becb991-932f-4433-a280-9df6f39b6194', 'v=spf1 -all', 'z-other-thing=this proves i have control over this domain']> (config)
*   Create <ARecord A 3600, *.my-domain.com., ['203.0.113.45']> (config)
*   Create <AaaaRecord AAAA 3600, *.my-domain.com., ['2001:db8::46']> (config)
*   Create <TxtRecord TXT 3600, nadcbiqkbgq._companyname.my-domain.com., ['a-different-proof-of-ownership']> (config)
*   Create <CnameRecord CNAME 3600, pointer.my-domain.com., look.over-here.net.> (config)
*   Create <ARecord A 3600, www.my-domain.com., ['203.0.113.42', '203.0.113.43']> (config)
*   Create <AaaaRecord AAAA 3600, www.my-domain.com., ['2001:db8::44']> (config)
*   Summary: Creates=9, Updates=0, Deletes=0, Existing Records=0
********************************************************************************
```

### Applying the changes

```console
(env) $ octodns-sync --config-file=config/octodns.yaml --doit
...
********************************************************************************
* unused-domain.io.
********************************************************************************
* powerdns (PowerDnsProvider)
*   Create Zone<unused-domain.io.>
*   Create <TxtRecord TXT 3600, unused-domain.io., ['v=spf1 -all']> ()
*   Summary: Creates=1, Updates=0, Deletes=0, Existing Records=0
********************************************************************************
* my-domain.com.
********************************************************************************
* powerdns (PowerDnsProvider)
*   Create Zone<my-domain.com.>
*   Create <ARecord A 3600, my-domain.com., ['203.0.113.42', '203.0.113.43']> (config)
*   Create <AaaaRecord AAAA 3600, my-domain.com., ['2001:db8::44']> (config)
*   Create <TxtRecord TXT 3600, my-domain.com., ['some-verification=3becb991-932f-4433-a280-9df6f39b6194', 'v=spf1 -all', 'z-other-thing=this proves i have control over this domain']> (config)
*   Create <ARecord A 3600, *.my-domain.com., ['203.0.113.45']> (config)
*   Create <AaaaRecord AAAA 3600, *.my-domain.com., ['2001:db8::46']> (config)
*   Create <TxtRecord TXT 3600, nadcbiqkbgq._companyname.my-domain.com., ['a-different-proof-of-ownership']> (config)
*   Create <CnameRecord CNAME 3600, pointer.my-domain.com., look.over-here.net.> (config)
*   Create <ARecord A 3600, www.my-domain.com., ['203.0.113.42', '203.0.113.43']> (config)
*   Create <AaaaRecord AAAA 3600, www.my-domain.com., ['2001:db8::44']> (config)
*   Summary: Creates=9, Updates=0, Deletes=0, Existing Records=0
********************************************************************************

2023-08-23T15:17:00  [4671815168] INFO  PowerDnsProvider[powerdns] apply: making 1 changes to unused-domain.io.
2023-08-23T15:17:00  [4671815168] INFO  PowerDnsProvider[powerdns] apply: making 9 changes to my-domain.com.
2023-08-23T15:17:00  [4671815168] INFO  Manager sync:   10 total changes
```

```console
(env) $ octodns-sync --config-file=config/octodns.yaml
********************************************************************************
No changes were planned
********************************************************************************
```

That's it. You're now managing your DNS with octoDNS.

## Making a change

At some point down the road you need to make a change, maybe one of your web
boxes was replaced and there's a new IP address. The first step is to open up
the zone's YAML file and modify the YAML, removing 203.0.113.42 and adding
203.0.113.44.

## Running octoDNS to see the plan

Just like during the first run section above we'll first run octoDNS to see what changes it would make.
We'd skim the log lines again looking for unexpected WARNINGS and then take a look at the changes.

```console
(env) $ octodns-sync --config-file=config/octodns.yaml
...
********************************************************************************
* my-domain.com.
********************************************************************************
* powerdns (PowerDnsProvider)
*   Create Zone<my-domain.com.>
*   Update
*     <ARecord A 3600, my-domain.com., ['203.0.113.42', '203.0.113.43']> ->
*     <ARecord A 3600, my-domain.com., ['203.0.113.43', '203.0.113.44']> (config)
*   Update
*     <ARecord A 3600, www.my-domain.com., ['203.0.113.42', '203.0.113.43']> ->
*     <ARecord A 3600, www.my-domain.com., ['203.0.113.43', '203.0.113.44']> (config)
*   Summary: Creates=0, Updates=2, Deletes=0, Existing Records=9
********************************************************************************
```

Since we have used YAML anchors to share the values across both the root and
www A's we see that octoDNS will be making changes to both those records.

If there were unexpected things here we'd need to investigate what's changed.
Maybe there were other alterations in the YAML that hadn't been applied yet or
someone modified the records through another means.

Here we only see the expected changes so we're good to move forward with
applying them.

```console
(env) $ octodns-sync --config-file=config/octodns.yaml --doit
...
********************************************************************************
* my-domain.com.
********************************************************************************
* powerdns (PowerDnsProvider)
*   Create Zone<my-domain.com.>
*   Update
*     <ARecord A 3600, my-domain.com., ['203.0.113.42', '203.0.113.43']> ->
*     <ARecord A 3600, my-domain.com., ['203.0.113.43', '203.0.113.44']> (config)
*   Update
*     <ARecord A 3600, www.my-domain.com., ['203.0.113.42', '203.0.113.43']> ->
*     <ARecord A 3600, www.my-domain.com., ['203.0.113.43', '203.0.113.44']> (config)
*   Summary: Creates=0, Updates=2, Deletes=0, Existing Records=9
********************************************************************************
```

If we want we can run another plan to make sure there are no further pending changes.

```console
(env) $ octodns-sync --config-file=config/octodns.yaml
********************************************************************************
No changes were planned
********************************************************************************
```

## What's Next

* Check out [migrating to octoDNS](../migrating-to-octodns/README.md) for an example of how to create zone configuration YAML files from your existing provider's configuration
* For a complete list check out the [Examples Directory](../README.rst)
