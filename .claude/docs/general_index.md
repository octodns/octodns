# General Index

## Root

- `.readthedocs.yaml` - Read the Docs configuration for building documentation [CONFIG]
- `README.md` - Project overview and documentation links for octoDNS [DOCS]
- `pyproject.toml` - Tooling configuration for black, isort, coverage, and pytest warnings [CONFIG]
- `requirements.txt` - Pinned Python dependencies for octoDNS development/testing [BUILD]

## docs/

- `api.rst` - Developer-facing API documentation index. [DOCS]
- `conf.py` - Sphinx configuration with logic to rewrite local links to the correct Git ref.. Key: `_detect_git_ref`, `_detect_docs_ref`, `_rewrite_repo_local_links`, `setup` [DOCS]
- `configuration.rst` - Main configuration guide covering providers, zones, and options. [DOCS]
- `dynamic_records.rst` - Documentation for dynamic/geo/weighted DNS record configuration. [DOCS]
- `dynamic_zone_config.rst` - Guide to matching and generating managed zones dynamically. [DOCS]
- `getting-started.rst` - Tutorial walkthrough for setting up and running octoDNS. [DOCS]
- `records.rst` - Documentation describing record models, validation, and record-level behaviors. [DOCS]
- `zone_lifecycle.rst` - Describes zone planning/apply lifecycle and key hooks. [DOCS]

## docs/api/

- `cmds.rst` - API docs index for CLI commands [DOCS]
- `helpers.rst` - API docs index for octoDNS helper modules [DOCS]
- `manager.rst` - Sphinx API doc entry for octodns.manager module [DOCS]
- `processors.rst` - API docs for processor configuration and available processors [DOCS]
- `providers.rst` - API docs index for provider base/plan/yaml modules [DOCS]
- `records.rst` - API docs index for supported DNS record types [DOCS]
- `secrets.rst` - API docs index for secret handling modules [DOCS]
- `sources.rst` - API docs index for DNS source modules [DOCS]
- `zone.rst` - Sphinx API doc entry for octodns.zone module [DOCS]

## octodns/

- `__init__.py` - Defines the octodns package version constants for external consumers.. Key: `__version__`, `__VERSION__` [SOURCE_CODE]
- `context.py` - Adds a context attribute to dicts used for record parsing/validation. Key: `class ContextDict`, `ContextDict.__init__` [SOURCE_CODE]
- `deprecation.py` - Utility for emitting standardized Python DeprecationWarnings. Key: `deprecated` [SOURCE_CODE]
- `equality.py` - Mixin implementing rich comparisons via an equality tuple. Key: `class EqualityTupleMixin`, `EqualityTupleMixin._equality_tuple`, `EqualityTupleMixin.__eq__`, `EqualityTupleMixin.__lt__` [SOURCE_CODE]
- `idna.py` - Utility helpers to encode/decode and case-insensitively store IDNA/UTF-8 DNS names.. Key: `IdnaError`, `encode`, `idna_encode`, `decode`, `idna_decode` [SOURCE_CODE]
- `manager.py` - Core orchestration for loading config, wiring plugins, processing zones, and running sync/dump plans.. Key: `_AggregateTarget`, `MainThreadExecutor`, `MakeThreadFuture`, `Manager`, `_build_kwargs` [SOURCE_CODE]
- `yaml.py` - YAML safe load/dump with !include support and optional key-order enforcement.. Key: `ContextLoader`, `SortEnforcingLoader`, `NaturalSortEnforcingLoader`, `SimpleSortEnforcingLoader`, `InvalidOrder` [SOURCE_CODE]
- `zone.py` - Zone container with record validation, copy-on-write, and diff computation. Key: `SubzoneRecordException`, `DuplicateRecordException`, `InvalidNodeException`, `InvalidNameError`, `Zone` [SOURCE_CODE]

## octodns/cmds/

- `__init__.py` - Package initializer for octodns CLI command implementations [SOURCE_CODE]
- `args.py` - Defines CLI argument parsing and sets up logging (stderr/stdout + optional syslog).. Key: `ArgumentParser`, `parse_args`, `_setup_logging` [SOURCE_CODE]
- `compare.py` - CLI command to compare two sources for DNS zone changes [CLI]
- `dump.py` - CLI command to dump DNS records from sources into files [CLI]
- `report.py` - CLI command to query DNS resolvers for OctoDNS zone records and emit CSV/JSON reports.. Key: `async_resolve`, `main` [CLI]
- `sync.py` - CLI command to plan/perform DNS sync between providers [CLI]
- `validate.py` - CLI command to validate DNS configs/records and fail on warnings. Key: `FlaggingHandler`, `main` [CLI]
- `versions.py` - CLI entrypoint for initializing manager to show/handle version info [CLI]

## octodns/processor/

- `__init__.py` - Package initializer for octodns processor components [SOURCE_CODE]
- `acme.py` - Processor that marks and ignores managed ACME TXT challenge records in zones. Key: `AcmeManagingProcessor`, `AcmeMangingProcessor` [SOURCE_CODE]
- `arpa.py` - Generates reverse (PTR) records for A/AAAA source records via automatic ARPA mapping.. Key: `AutoArpa`, `__init__`, `process_source_zone`, `_order_and_unique_fqdns`, `populate` [SOURCE_CODE]
- `base.py` - Defines BaseProcessor hooks and ProcessorException for octoDNS processing stages.. Key: `ProcessorException`, `BaseProcessor`, `process_source_zone`, `process_target_zone`, `process_source_and_target_zones` [SOURCE_CODE]
- `clamp.py` - Processor that clamps record TTLs to a configured min/max range.. Key: `TTLArgumentException`, `TtlClampProcessor`, `process_source_zone` [SOURCE_CODE]
- `filter.py` - Zone/plan processors to allow/reject records by type, name, value, network, or NS rules.. Key: `_FilterProcessor`, `AllowsMixin`, `RejectsMixin`, `_TypeBaseFilter`, `TypeAllowlistFilter` [SOURCE_CODE]
- `meta.py` - Processor that injects/updates a TXT meta record containing run/provider/version metadata.. Key: `MetaProcessor`, `get_time`, `get_uuid`, `values`, `process_source_and_target_zones` [SOURCE_CODE]
- `ownership.py` - Processor that injects TXT ownership records and filters plan changes to those owned.. Key: `OwnershipProcessor`, `process_source_zone`, `process_plan`, `_is_ownership` [SOURCE_CODE]
- `restrict.py` - Processor that restricts record TTL values within min/max or an allowed set.. Key: `RestrictionException`, `TtlRestrictionFilter`, `process_source_zone` [SOURCE_CODE]
- `spf.py` - Processor validating SPF TXT records via DNS lookup count and mechanism checks.. Key: `SpfDnsLookupProcessor`, `SpfValueException`, `SpfDnsLookupException`, `_get_spf_from_txt_values`, `_process_answer` [SOURCE_CODE]
- `templating.py` - Processor that applies python .format-style templating to record values.. Key: `TemplatingError`, `Templating`, `process_source_and_target_zones` [SOURCE_CODE]
- `trailing_dots.py` - Processor that appends missing trailing dots to specific DNS record fields.. Key: `_no_trailing_dot`, `_ensure_trailing_dots`, `EnsureTrailingDots`, `process_source_zone` [SOURCE_CODE]

## octodns/provider/

- `__init__.py` - Provider-related exception types for octoDNS. Key: `ProviderException`, `SupportsException` [SOURCE_CODE]
- `base.py` - Abstract provider base implementing provider-specific desired/existing processing and plan workflow. Key: `BaseProvider`, `_process_desired_zone`, `_process_existing_zone`, `_include_change`, `_extra_changes` [SOURCE_CODE]
- `plan.py` - Defines Plan safety checks and renderers (logger/json/markdown/html) for planned DNS changes.. Key: `UnsafePlan`, `RootNsChange`, `TooMuchChange`, `Plan`, `_custom_fh` [SOURCE_CODE]
- `yaml.py` - Provider that loads and writes DNS zone records from YAML files on disk.. Key: `YamlProvider`, `list_zones`, `populate`, `_apply`, `_split_sources` [SOURCE_CODE]

## octodns/record/

- `__init__.py` - Exports all DNS record and value classes as the octodns.record public API.. Key: `ARecord`, `AaaaRecord`, `AliasRecord`, `Record`, `Change` [SOURCE_CODE]
- `a.py` - Implements DNS A record backed by IPv4 address value type. Key: `Ipv4Value`, `ARecord`, `Record.register_type(ARecord)` [SOURCE_CODE]
- `aaaa.py` - Implements DNS AAAA record backed by IPv6 address value type. Key: `Ipv6Value`, `AaaaRecord`, `Record.register_type(AaaaRecord)` [SOURCE_CODE]
- `alias.py` - Implements ALIAS DNS record with target semantics and root restriction. Key: `AliasValue`, `AliasRecord`, `AliasRecord.validate`, `Record.register_type(AliasRecord)` [SOURCE_CODE]
- `base.py` - Core DNS Record base with type registration, validation, copy/data, and shared mixins.. Key: `unquote`, `Record`, `Record.register_type`, `Record.registered_types`, `Record.new` [SOURCE_CODE]
- `caa.py` - Implements RFC6844 CAA record value parsing, validation, and formatting. Key: `CaaValue.parse_rdata_text`, `CaaValue.validate`, `CaaValue._equality_tuple`, `CaaRecord`, `Record.register_type` [SOURCE_CODE]
- `change.py` - Models plan changes (create/update/delete) with stable equality. Key: `class Change`, `Change.record`, `Change._equality_tuple`, `class Create`, `class Update` [SOURCE_CODE]
- `chunked.py` - Chunking/escaping helpers for TXT/SPF-like values and a wrapper value type.. Key: `_ChunkedValuesMixin`, `chunked_value`, `chunked_values`, `rr_values`, `_ChunkedValue` [SOURCE_CODE]
- `cname.py` - Implements CNAME DNS record with root restriction. Key: `CnameValue`, `CnameRecord`, `CnameRecord.validate`, `Record.register_type(CnameRecord)` [SOURCE_CODE]
- `dname.py` - Implements DNAME DNS record backed by target value type. Key: `DnameValue`, `DnameRecord`, `Record.register_type(DnameRecord)` [SOURCE_CODE]
- `ds.py` - Implements DNSSEC DS record value parsing, validation, and legacy support. Key: `DsValue.parse_rdata_text`, `DsValue.validate`, `DsValue.__init__`, `DsValue.template`, `DsRecord` [SOURCE_CODE]
- `dynamic.py` - Implements validation and parsing/serialization for dynamic geo/subnet DNS records. Key: `_DynamicPool`, `_DynamicRule`, `_DynamicMixin._validate_pools`, `_DynamicMixin._validate_rules`, `_DynamicMixin.validate` [SOURCE_CODE]
- `exception.py` - Defines record-specific exceptions and validation error formatting. Key: `RecordException`, `ValidationError.build_message`, `ValidationError.__init__` [SOURCE_CODE]
- `geo.py` - Adds (deprecated) GeoDNS support via geo value parsing and record changes. Key: `GeoCodes.validate`, `GeoCodes.parse`, `GeoCodes.country_to_code`, `GeoCodes.province_to_code`, `class GeoValue` [SOURCE_CODE]
- `geo_data.py` - Generated hierarchy of geo continent/country/province codes. Key: `geo_data` [GENERATED]
- `https.py` - Defines HTTPS record as an alias of SVCB values for HTTPS RR. Key: `HttpsValue`, `HttpsRecord`, `Record.register_type` [SOURCE_CODE]
- `ip.py` - Provides a shared IP value type with parsing/validation/normalization. Key: `_IpValue.parse_rdata_text`, `_IpValue.validate`, `_IpValue.process`, `_IpValue.__new__`, `_IpAddress` [SOURCE_CODE]
- `loc.py` - Implements LOC record value parsing, validation, and formatting. Key: `LocValue.parse_rdata_text`, `LocValue.validate`, `LocValue.__init__`, `LocValue.rdata_text`, `LocValue._equality_tuple` [SOURCE_CODE]
- `mx.py` - MX record value parsing/validation with IDNA encoding and templated exchange support.. Key: `MxValue`, `parse_rdata_text`, `validate`, `process`, `template` [SOURCE_CODE]
- `naptr.py` - NAPTR record value parsing/validation, rendering to RFC text, and templating.. Key: `NaptrValue`, `parse_rdata_text`, `validate`, `process`, `__init__` [SOURCE_CODE]
- `ns.py` - NS record type implementation using multi-target values. Key: `NsValue`, `NsRecord`, `Record.register_type` [SOURCE_CODE]
- `openpgpkey.py` - Implements OPENPGPKEY record handling for base64 OpenPGP keys. Key: `OpenpgpkeyValue.parse_rdata_text`, `OpenpgpkeyValue.validate`, `OpenpgpkeyValue.process`, `OpenpgpkeyRecord`, `Record.register_type` [SOURCE_CODE]
- `ptr.py` - PTR record implementation with backward-compatible single-value property. Key: `PtrValue`, `PtrRecord`, `PtrRecord.value`, `Record.register_type` [SOURCE_CODE]
- `rr.py` - Shared RFC-style RR container used by Record.from_rrs. Key: `RrParseError`, `Rr` [SOURCE_CODE]
- `spf.py` - SPF record type wrapper (deprecated in favor of TXT). Key: `SpfRecord`, `deprecated`, `Record.register_type` [SOURCE_CODE]
- `srv.py` - Implements SRV record value parsing, validation, templating, and registration.. Key: `SrvValue`, `parse_rdata_text`, `validate`, `template`, `SrvRecord` [SOURCE_CODE]
- `sshfp.py` - Implements SSHFP record value parsing, validation, and equality. Key: `SshfpValue.parse_rdata_text`, `SshfpValue.validate`, `SshfpValue.template`, `SshfpValue._equality_tuple`, `SshfpRecord` [SOURCE_CODE]
- `subnet.py` - Subnet parsing/validation helper for dynamic rule targeting. Key: `Subnets.validate`, `Subnets.parse` [SOURCE_CODE]
- `svcb.py` - Implements RFC 9460 SVCB record parsing/validation/rendering and supported SvcParams.. Key: `SUPPORTED_PARAMS`, `validate_svcparam_alpn`, `validate_svcparam_ipv4hint`, `validate_svcparam_ipv6hint`, `validate_svcparam_mandatory` [SOURCE_CODE]
- `target.py` - Shared target/hostname validation and value classes with IDNA handling and templating.. Key: `validate_target_fqdn`, `_TargetValue`, `_TargetsValue` [SOURCE_CODE]
- `tlsa.py` - Implements TLSA record value parsing, validation, and templating. Key: `TlsaValue.parse_rdata_text`, `TlsaValue.validate`, `TlsaValue.__init__`, `TlsaValue.template`, `TlsaRecord` [SOURCE_CODE]
- `txt.py` - TXT record type implementation using chunked values. Key: `TxtValue`, `TxtRecord`, `Record.register_type` [SOURCE_CODE]
- `uri.py` - Implements URI DNS record type parsing, validation, and rendering. Key: `UriValue.parse_rdata_text`, `UriValue.validate`, `UriValue.__init__`, `UriValue.template`, `UriRecord.validate` [SOURCE_CODE]
- `urlfwd.py` - Implements URLFWD DNS record type parsing, validation, and rendering. Key: `UrlfwdValue.parse_rdata_text`, `UrlfwdValue.validate`, `UrlfwdValue.rdata_text`, `UrlfwdValue.template`, `UrlfwdRecord` [SOURCE_CODE]

## octodns/secret/

- `__init__.py` - Package initializer for octodns secret-handling components [SOURCE_CODE]
- `base.py` - Base class for secret integrations with per-instance logging. Key: `BaseSecrets`, `BaseSecrets.__init__` [SOURCE_CODE]
- `environ.py` - Resolves secrets from OS environment variables with optional defaults and type coercion.. Key: `EnvironSecretsException`, `EnvironSecrets`, `fetch` [SOURCE_CODE]
- `exception.py` - Defines base exception type for the octodns secret subsystem. Key: `SecretsException` [SOURCE_CODE]

## octodns/source/

- `__init__.py` - Package initializer for octodns source/provider input components [SOURCE_CODE]
- `base.py` - Abstract base class for octoDNS sources/providers loading DNS data. Key: `class BaseSource`, `BaseSource.__init__`, `BaseSource.populate`, `BaseSource.supports`, `BaseSource.SUPPORTS_DYNAMIC` [SOURCE_CODE]
- `envvar.py` - Source that embeds environment variables into generated TXT records. Key: `EnvironmentVariableNotFoundException`, `EnvVarSource`, `EnvVarSource._read_variable`, `EnvVarSource.populate` [SOURCE_CODE]
- `tinydns.py` - Imports legacy TinyDNS zone files into octoDNS records. Key: `_unique`, `TinyDnsBaseSource`, `TinyDnsBaseSource.SYMBOL_MAP`, `TinyDnsBaseSource._process_lines`, `TinyDnsBaseSource._process_symbols` [SOURCE_CODE]

## tests/

- `config-secrets.yaml` - Test configuration for secret handlers with env and cross-handler dependency rules [CONFIG]
- `helpers.py` - Test helper utilities: dummy sources/providers and small framework helpers. Key: `SimpleProvider`, `GeoProvider`, `DynamicProvider`, `TemporaryDirectory`, `CountingProcessor` [TEST]
- `test_octodns_equality.py` - Unit tests for EqualityTupleMixin comparison semantics. Key: `TestEqualityTupleMixin`, `test_basics`, `test_not_implemented` [TEST]
- `test_octodns_idna.py` - Unit tests for IDNA encoding/decoding and IdnaDict behavior. Key: `TestIdna`, `TestIdnaDict`, `assertIdna` [TEST]
- `test_octodns_manager.py` - Integration-style unit tests validating Manager orchestration, config validation, IDNA, checksum gating, and dump/sync behaviors.. Key: `TestManager` [TEST]
- `test_octodns_processor_acme.py` - Tests ACME managing processor for TXT ownership and ignore/go-away behavior. Key: `TestAcmeManagingProcessor`, `test_process_zones`, `AcmeManagingProcessor.process_source_zone`, `AcmeManagingProcessor.process_target_zone` [TEST]
- `test_octodns_processor_arpa.py` - Unit tests for AutoArpa processor PTR generation logic including wildcard/geo/dynamic.. Key: `TestAutoArpa`, `test_empty_zone`, `test_single_value_A`, `test_multi_value_A`, `test_AAAA` [TEST]
- `test_octodns_processor_clamp.py` - Tests TTL clamp processor behavior for min/max bounds and argument validation. Key: `TestClampProcessor`, `test_processor_min`, `test_processor_max`, `test_processor_maxmin`, `test_processor_minmax` [TEST]
- `test_octodns_processor_ownership.py` - Unit tests verifying OwnershipProcessor ownership TXT generation and plan filtering logic.. Key: `TestOwnershipProcessor`, `test_process_source_zone`, `test_process_plan`, `test_remove_last_change`, `test_should_replace` [TEST]
- `test_octodns_processor_restrict.py` - Tests TTL restriction filter enforcing min/max and allowed TTL lists. Key: `TestTtlRestrictionFilter`, `test_restrict_ttl`, `TtlRestrictionFilter.process_source_zone` [TEST]
- `test_octodns_processor_spf.py` - Tests SPF DNS lookup processor resolving include mechanisms and error cases. Key: `TestSpfDnsLookupProcessor`, `_get_spf_from_txt_values`, `test_processor`, `test_processor_with_long_txt_value`, `test_processor_with_lenient_record` [TEST]
- `test_octodns_processor_trailing_dots.py` - Unit tests for EnsureTrailingDots normalization and value-type preservation.. Key: `EnsureTrailingDotsTest` [TEST]
- `test_octodns_record.py` - Unit tests for Record base factory/validation, IDNA handling, copy isolation, and ordering semantics.. Key: `TestRecord` [TEST]
- `test_octodns_record_a.py` - Tests A record/value validation, equality, changes, and error handling. Key: `TestRecordA`, `test_a_and_record`, `test_validation_and_values_mixin` [TEST]
- `test_octodns_record_aaaa.py` - Unit tests for AAAA record parsing, IPv6 normalization, and validation. Key: `TestRecordAaaa`, `assertMultipleValues`, `test_aaaa`, `test_validation` [TEST]
- `test_octodns_record_alias.py` - Tests ALIAS record behavior, validation rules, and templating interactions. Key: `TestRecordAlias`, `test_alias`, `test_alias_lowering_value`, `test_validation_and_value_mixin`, `test_template_validation` [TEST]
- `test_octodns_record_caa.py` - Tests CAA record/value parsing, equality, diffing, and validation. Key: `TestRecordCaa`, `test_caa`, `test_caa_value_rdata_text`, `test_validation`, `TestCaaValue` [TEST]
- `test_octodns_record_change.py` - Unit tests for deterministic sorting of record change objects. Key: `TestChanges`, `test_sort_same_change_type`, `test_sort_same_different_type` [TEST]
- `test_octodns_record_chunked.py` - Tests chunked TXT/SPF value parsing, validation, chunk splitting, and templating.. Key: `TestRecordChunked`, `TestChunkedValue`, `test_chunked_value_rdata_text`, `test_validate`, `test_splitting` [TEST]
- `test_octodns_record_cname.py` - Tests CNAME record behavior, validation, and templating substitution rules. Key: `TestRecordCname`, `assertSingleValue`, `test_validation`, `test_template_validation` [TEST]
- `test_octodns_record_dname.py` - Tests DNAME record behavior, validation, and templating substitution rules. Key: `TestRecordDname`, `assertSingleValue`, `test_validation`, `test_template_validation` [TEST]
- `test_octodns_record_ds.py` - Tests DS record/value parsing, ordering, validation, and templating. Key: `TestRecordDs`, `test_ds`, `TestDsValue`, `test_template` [TEST]
- `test_octodns_record_dynamic.py` - Unit tests for dynamic record behavior and protocol-specific healthcheck semantics.. Key: `TestRecordDynamic` [TEST]
- `test_octodns_record_geo.py` - Unit tests for geo-enabled records, geo code parsing/validation, and change impact. Key: `TestRecordGeo`, `TestRecordGeoCodes` [TEST]
- `test_octodns_record_ip.py` - Tests IP record value parsing (noop) and IPv4 templating behavior. Key: `TestRecordIp`, `test_ipv4_value_rdata_text`, `TestIpValue`, `test_template` [TEST]
- `test_octodns_record_loc.py` - Tests LOC record/value parsing, ordering, diffs, and validation. Key: `TestRecordLoc`, `test_loc`, `test_loc_value_rdata_text`, `test_loc_value`, `test_validation` [TEST]
- `test_octodns_record_mx.py` - Unit tests for MX record parsing, validation, and change detection. Key: `TestRecordMx`, `TestMxValue` [TEST]
- `test_octodns_record_naptr.py` - Unit tests for NAPTR record parsing, validation, comparison, and templating. Key: `TestRecordNaptr`, `test_naptr`, `test_naptr_value_rdata_text`, `test_validation`, `test_flags_case_insensitive` [TEST]
- `test_octodns_record_ns.py` - Unit tests for NS record parsing, validation, and templating behavior. Key: `TestRecordNs`, `test_ns`, `test_validation`, `test_template_validation` [TEST]
- `test_octodns_record_openpgpkey.py` - Unit tests for OPENPGPKEY record parsing, base64 normalization, and changes. Key: `TestRecordOpenpgpkey`, `test_openpgpkey_value_rdata_text`, `test_changes`, `TestOpenpgpkeyValue` [TEST]
- `test_octodns_record_ptr.py` - Unit tests for PTR record parsing, FQDN validation, and templating behavior. Key: `TestRecordPtr`, `test_ptr_lowering_value`, `test_ptr`, `test_template_validation` [TEST]
- `test_octodns_record_spf.py` - Unit tests for SPF record parsing and escape/validation rules. Key: `TestRecordSpf`, `assertMultipleValues`, `test_validation` [TEST]
- `test_octodns_record_srv.py` - Unit tests for SRV record parsing, validation, and change detection. Key: `TestRecordSrv`, `TestSrvValue` [TEST]
- `test_octodns_record_sshfp.py` - Tests SSHFP record/value parsing, equality, diffs, templating, validation. Key: `TestRecordSshfp`, `test_sshfp`, `test_sshfp_value_rdata_text`, `test_validation`, `TestSshFpValue` [TEST]
- `test_octodns_record_target.py` - Unit tests for target value wrappers used by records like ALIAS/targets. Key: `TestRecordTarget`, `TestTargetValue`, `TestTargetsValue` [TEST]
- `test_octodns_record_tlsa.py` - Unit tests for TLSA record values, parsing, validation, and changes. Key: `TestRecordTlsa`, `test_tlsa`, `test_tsla_value_rdata_text`, `TestTlsaValue` [TEST]
- `test_octodns_record_txt.py` - Unit tests for TXT record chunking, quoting, RR formatting, and validation. Key: `TestRecordTxt`, `test_long_value_chunking`, `test_rr` [TEST]
- `test_octodns_record_uri.py` - Tests URI record/value parsing, equality, diffs, templating, and validation. Key: `TestRecordUri`, `test_uri`, `test_uri_value_rdata_text`, `test_valiation`, `TestUriValue` [TEST]
- `test_octodns_record_urlfwd.py` - Tests URLFWD record/value parsing, equality, diffs, validation. Key: `TestRecordUrlfwd`, `test_urlfwd`, `test_urlfwd_value_rdata_text`, `test_validation`, `TestUrlfwdValue` [TEST]
- `test_octodns_secret_environ.py` - Unit tests for EnvironSecrets fetching env vars with default values and numeric coercion.. Key: `TestEnvironSecrets` [TEST]
- `test_octodns_source_envvar.py` - Unit tests for EnvVarSource that builds TXT records from environment variables. Key: `TestEnvVarSource`, `test_read_variable`, `test_populate` [TEST]
- `test_octodns_source_tinydns.py` - Integration-ish unit tests for TinyDnsFileSource zone file parsing. Key: `TestTinyDnsFileSource`, `test_populate_normal`, `test_populate_in_addr_arpa`, `test_ignores_subs` [TEST]
- `test_octodns_yaml.py` - Unit tests for octodns.yaml safe_load/safe_dump ordering and include/merge behavior.. Key: `TestYaml`, `test_stuff`, `test_include`, `test_include_merge`, `test_order_mode` [TEST]
- `test_octodns_zone.py` - Unit tests covering Zone record validation, sub-zone rules, diffing, and IDNA behaviors. Key: `TestZone` [TEST]

## tests/config/

- `alias-zone-loop.yaml` - Test config exercising alias zone loops in zone resolution [CONFIG]
- `always-dry-run.yaml` - Test config for per-zone always-dry-run behavior [CONFIG]
- `bad-plan-output-config.yaml` - Fixture: invalid plan_outputs configuration for PlanLogger class [TEST]
- `bad-plan-output-missing-class.yaml` - Bad-plan-output fixture missing required plan output class [TEST]
- `bad-provider-class-module.yaml` - Config fixture for provider class with missing module path [TEST]
- `bad-provider-class-no-module.yaml` - Config fixture for provider class with missing module qualifier [TEST]
- `bad-provider-class.yaml` - Config fixture for provider class that does not exist [TEST]
- `dump-processors.yaml` - Test config defining processors and a dump target provider [CONFIG]
- `dynamic-arpa-no-normal-source.yaml` - Fixture: dynamic auto-arpa populating when normal sources are absent [TEST]
- `dynamic-arpa.yaml` - Fixture: dynamic ARPA zones with auto-arpa population and merge sources [TEST]
- `dynamic-config-no-list-zones.yaml` - Fixture: dynamic config requiring list_zones but provider does not support it [TEST]
- `dynamic-config.yaml` - Test config for dynamic manager/config fields and None handling [CONFIG]
- `dynamic.tests.yaml` - Fixture: extensive dynamic routing policies for multiple record types [TEST]
- `empty.yaml` - Empty YAML configuration fixture [TEST]
- `missing-provider-class.yaml` - Config fixture with provider missing required 'class' field [TEST]
- `missing-provider-config.yaml` - Config fixture with provider class but no other required provider settings [TEST]
- `missing-provider-env.yaml` - Fixture: provider points to missing directory for env/YAML input [TEST]
- `missing-sources.yaml` - Config fixture with zones present but missing sources configuration [TEST]
- `no-dump.yaml` - Fixture: output provider configured but without dump usage edge cases [TEST]
- `plan-output-filehandle.yaml` - Fixture: plan_outputs entry referencing a nonexistent plan logger class [TEST]
- `processors-missing-class.yaml` - Fixture: processors list contains entry with missing class name [TEST]
- `processors-wants-config.yaml` - Fixture: processor configured with class that requires params (missing config) [TEST]
- `processors.yaml` - Fixture: processor registration, selection, and counting coverage [TEST]
- `provider-problems.yaml` - Fixture: provider/zone misconfigurations (missing sources/targets/unknowns) [TEST]
- `simple-alias-zone.yaml` - Fixture: zone aliasing from one.tests to unit.tests [TEST]
- `simple-arpa.yaml` - Fixture: auto-arpa generation for IPv4/IPv6 reverse zones [TEST]
- `simple-split.yaml` - Fixture: SplitYamlProvider with multiple targets and subzones [TEST]
- `simple-validate.yaml` - Minimal YAML config used to validate provider/zone wiring. [CONFIG]
- `simple.yaml` - Integration-style YAML config exercising multiple providers and targets. [CONFIG]
- `sub.txt.unit.tests.yaml` - Unit test fixture YAML placeholder for sub.txt tests [TEST]
- `subzone.unit.tests.yaml` - DNS record fixture for a subzone in unit tests [TEST]
- `unit.tests.yaml` - Fixture YAML containing a full set of DNS records for unit.tests. [DATA]
- `unknown-processor.yaml` - Config fixture to test behavior when an unknown processor is referenced. [CONFIG]
- `unknown-provider.yaml` - Config fixture to test behavior when a zone references a missing source provider. [CONFIG]
- `unknown-source-zone.yaml` - Config fixture to test error when an alias points to an unknown zone. [CONFIG]
- `unordered.yaml` - YAML fixture with intentionally unordered record fields [TEST]

## tests/config-semis/

- `escaped.semis.yaml` - Fixture testing escaped semicolons in YAML values [TEST]
- `unescaped.semis.yaml` - Fixture testing unescaped semicolons in YAML values [TEST]

## tests/config/dynamic-arpa/

- `3.2.2.in-addr.arpa.yaml` - Empty YAML fixture for dynamic ARPA zone 3.2.2.in-addr.arpa [TEST]
- `b.e.f.f.f.d.1.8.f.2.6.0.1.2.e.0.0.5.0.4.4.6.0.1.0.6.2.ip6.arpa.yaml` - Empty YAML fixture for dynamic IPv6 ARPA zone [TEST]
- `unit.tests.yaml` - Fixture zone YAML for dynamic arpa/PTR-related tests. [DATA]

## tests/config/hybrid/

- `one.test.yaml` - Hybrid zone file fixture containing a TXT record [TEST]

## tests/config/hybrid/two.test./

- `$two.test.yaml` - Hybrid fixture for a root-hierarchy TXT record under two.test. [TEST]
- `split-zone-file.yaml` - Hybrid fixture for split-zone-file TXT record under two.test. [TEST]

## tests/config/include/

- `array.yaml` - YAML fixture providing an array include target [TEST]
- `dict.yaml` - Included dictionary fixture used by YAML include tests [TEST]
- `dict_too.yaml` - Fixture used to test !include behavior with out-of-order keys [TEST]
- `empty.yaml` - YAML fixture providing an empty include target [TEST]
- `include-array-with-dict.yaml` - Fixture testing !include of a mix of array and dict files [TEST]
- `include-array-with-non-existant.yaml` - Fixture that includes a missing file to test include error handling [TEST]
- `include-array-with-unsupported.yaml` - Fixture that includes an unsupported nested path target [TEST]
- `include-dict-with-array.yaml` - Fixture testing !include used to build a dict that includes multiple files [TEST]
- `include-doesnt-exist.yaml` - YAML fixture referencing a non-existent include file [TEST]
- `main.yaml` - Root YAML fixture composing multiple !include inputs [TEST]
- `merge.yaml` - Fixture validating YAML merge keys with an included dict [TEST]
- `nested.yaml` - YAML fixture for nested include usage via custom tag [TEST]

## tests/config/include/subdir/

- `value.yaml` - Included YAML fragment containing plain text fixture content [TEST]

## tests/config/override/

- `dynamic.tests.yaml` - Fixture YAML providing overrides for dynamic.tests records. [DATA]

## tests/config/split/

- `shared.yaml` - Fixture record for shared TXT value used in split configuration tests [TEST]
- `unit.tests.yaml` - Fixture record for unit TXT value used when zone-file processing is enabled [TEST]

## tests/config/split/dynamic.tests.tst/

- `a.yaml` - Dynamic A record split fixture with geo pools and weights [CONFIG]
- `aaaa.yaml` - Dynamic AAAA record split fixture with geo pools and weights [CONFIG]
- `cname.yaml` - Dynamic CNAME split fixture with geo pools and weighted targets [CONFIG]
- `real-ish-a.yaml` - Fixture for dynamic A records with geo rules and weighted regional pools [TEST]
- `simple-weighted.yaml` - Fixture for dynamic CNAME weighted routing with a single default pool [TEST]

## tests/config/split/subzone.unit.tests.tst/

- `12.yaml` - Subzone fixture defining A record for label '12' in unit.tests.tst [TEST]
- `2.yaml` - Subzone fixture defining A record for label '2' in unit.tests.tst [TEST]
- `test.yaml` - Subzone fixture defining A record for label 'test' in unit.tests.tst [TEST]

## tests/config/split/unit.tests.tst/

- `$unit.tests.yaml` - Fixture defining multiple DNS record types for the unit.tests zone [TEST]
- `_srv._tcp.yaml` - Fixture for SRV record values under _srv._tcp subdomain [TEST]
- `aaaa.yaml` - Fixture defining an AAAA record for unit.tests.tst [TEST]
- `cname.yaml` - Fixture defining a CNAME record for unit.tests.tst [TEST]
- `dname.yaml` - Fixture defining a DNAME record for unit.tests.tst [TEST]
- `excluded.yaml` - Fixture for a CNAME record marked as excluded via octodns metadata [TEST]
- `ignored.yaml` - Fixture for an A record marked ignored via octodns metadata [TEST]
- `included.yaml` - YAML fixture defining an included CNAME record for unit.tests.tst [TEST]
- `mx.yaml` - Fixture for MX record set with preferences and multiple exchanges [TEST]
- `naptr.yaml` - Fixture for NAPTR record values with regex and service fields [TEST]
- `ptr.yaml` - YAML fixture defining a PTR record for unit.tests.tst [TEST]
- `spf.yaml` - YAML fixture defining an SPF record for unit.tests.tst [TEST]
- `sub.yaml` - YAML fixture defining an NS record with multiple targets [TEST]
- `txt.yaml` - Fixture for TXT record set including escaped/complex strings [TEST]
- `urlfwd.yaml` - Fixture for URLFWD records with redirect codes and masking [TEST]
- `www.sub.yaml` - YAML fixture defining an A record for www.sub [TEST]
- `www.yaml` - YAML fixture defining an A record for www [TEST]

## tests/config/split/unordered.tst/

- `abc.yaml` - YAML fixture defining a basic A record for abc [TEST]
- `xyz.yaml` - YAML fixture defining an A record with unordered keys [TEST]

## tests/zones/

- `2.0.192.in-addr.arpa.` - Fixture DNS reverse zone with SOA, NS, and PTR records [DATA]
- `ext.unit.tests.extension` - Fixture DNS extension zone with SOA and NS records only [DATA]
- `invalid.records.tst` - Fixture DNS zone containing intentionally questionable/invalid records [DATA]
- `invalid.zone.tst` - Fixture DNS zone with only SOA to trigger invalid-zone behavior [DATA]
- `unit.tests.tst` - Primary DNS zone fixture with broad record-type coverage [DATA]


---
*This knowledge base was extracted by [Codeset](https://codeset.ai) and is available via `python .claude/docs/get_context.py <file_or_folder>`*
