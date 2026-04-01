# General Index

## Root

- `.readthedocs.yaml` - ReadTheDocs build configuration for the project [CONFIG]
- `README.md` - Project overview and documentation entry point for octoDNS [DOCS]
- `pyproject.toml` - Project formatting, coverage, import sorting, and pytest warning settings. [BUILD]
- `requirements.txt` - Pinned Python dependencies for octoDNS [BUILD]

## docs/

- `api.rst` - Sphinx entrypoint for developer API documentation [DOCS]
- `conf.py` - Sphinx configuration with dynamic GitHub source-link rewriting for docs builds. Key: `_detect_git_ref`, `_detect_docs_ref`, `_rewrite_repo_local_links`, `setup` [DOCS]
- `configuration.rst` - Documentation for octoDNS configuration patterns and options [DOCS]
- `dynamic_records.rst` - Documentation for geo/weighted dynamic record configuration [DOCS]
- `dynamic_zone_config.rst` - Documentation for wildcard-based dynamic zone matching rules [DOCS]
- `getting-started.rst` - Tutorial-style guide for installing and running octoDNS [DOCS]
- `index.rst` - Main documentation index for octoDNS with overview and links [DOCS]
- `records.rst` - Documentation for record model, validation, and configuration schema [DOCS]
- `zone_lifecycle.rst` - Documentation of Zone sync lifecycle and plan/apply phases [DOCS]

## docs/api/

- `cmds.rst` - Sphinx API docs index for octoDNS CLI commands [DOCS]
- `helpers.rst` - Sphinx API docs index for helper modules [DOCS]
- `manager.rst` - Sphinx API doc stub for octodns.manager. [DOCS]
- `processors.rst` - Documentation for configuring and applying OctoDNS processors. [DOCS]
- `providers.rst` - API docs index for OctoDNS provider modules. [DOCS]
- `records.rst` - API docs index for OctoDNS record types. [DOCS]
- `secrets.rst` - API docs index for OctoDNS secret backends. [DOCS]
- `sources.rst` - API docs index for OctoDNS source modules. [DOCS]
- `zone.rst` - Sphinx API doc stub for octodns.zone. [DOCS]

## octodns/

- `__init__.py` - Defines the package version metadata for OctoDNS.. Key: `__version__`, `__VERSION__` [SOURCE_CODE]
- `context.py` - Dict wrapper that carries extra context for record processing errors. Key: `ContextDict`, `ContextDict.__init__` [SOURCE_CODE]
- `deprecation.py` - Utility for emitting DeprecationWarning with configurable stacklevel. Key: `deprecated` [SOURCE_CODE]
- `equality.py` - Mixin providing total ordering and equality based on _equality_tuple(). Key: `EqualityTupleMixin._equality_tuple`, `EqualityTupleMixin.__eq__`, `EqualityTupleMixin.__lt__`, `EqualityTupleMixin.__ge__` [SOURCE_CODE]
- `idna.py` - Utility helpers for IDNA encode/decode and a case/IDNA-insensitive mapping.. Key: `IdnaError`, `encode`, `idna_encode`, `decode`, `idna_decode` [SOURCE_CODE]
- `manager.py` - Core orchestration for octoDNS sync/dump/compare: config->zones->sources->processors->plans.. Key: `Manager`, `_AggregateTarget`, `MainThreadExecutor`, `MakeThreadFuture`, `ManagerException` [SOURCE_CODE]
- `yaml.py` - YAML helpers providing include/merge flattening plus optional key-order enforcement and sorted dumping.. Key: `ContextLoader`, `SortEnforcingLoader`, `NaturalSortEnforcingLoader`, `SimpleSortEnforcingLoader`, `safe_load` [SOURCE_CODE]
- `zone.py` - Core Zone domain object for DNS records: validation, diffing, and applying changes.. Key: `SubzoneRecordException`, `DuplicateRecordException`, `InvalidNodeException`, `InvalidNameError`, `Zone` [SOURCE_CODE]

## octodns/cmds/

- `__init__.py` - CLI commands package initializer [SOURCE_CODE]
- `args.py` - CLI argument parsing with logging configuration and verbosity controls.. Key: `ArgumentParser`, `parse_args`, `_setup_logging` [CLI]
- `compare.py` - CLI command to compare planned changes between two DNS sources.. Key: `main` [CLI]
- `dump.py` - CLI command to dump DNS zone data from configured sources.. Key: `main` [CLI]
- `report.py` - CLI command that queries DNS resolvers for a configured zone and outputs CSV/JSON reports.. Key: `async_resolve`, `main` [CLI]
- `sync.py` - CLI command to synchronize DNS records with optional safety checks.. Key: `main` [CLI]
- `validate.py` - CLI command to validate configs and fail on validation warnings.. Key: `FlaggingHandler`, `FlaggingHandler.handle`, `main` [CLI]
- `versions.py` - CLI command to load config and trigger version/report behavior.. Key: `main` [CLI]

## octodns/processor/

- `__init__.py` - Processor package initializer [SOURCE_CODE]
- `acme.py` - Processor that tags managed ACME TXT challenges and ignores unowned ones on targets.. Key: `AcmeManagingProcessor`, `process_source_zone`, `process_target_zone`, `AcmeMangingProcessor` [SOURCE_CODE]
- `arpa.py` - Auto-generate reverse (PTR) records for A/AAAA inputs in ARPA zones.. Key: `AutoArpa`, `process_source_zone`, `_order_and_unique_fqdns`, `populate`, `list_zones` [SOURCE_CODE]
- `base.py` - Defines BaseProcessor and ProcessorException for zone/plan processing hooks.. Key: `ProcessorException`, `BaseProcessor`, `process_source_zone`, `process_target_zone`, `process_source_and_target_zones` [SOURCE_CODE]
- `clamp.py` - Processor that clamps record TTLs to a configured min/max range.. Key: `TTLArgumentException`, `TtlClampProcessor`, `process_source_zone` [SOURCE_CODE]
- `filter.py` - DNS zone record filter processors for include/allow/reject and plan validation.. Key: `_FilterProcessor`, `AllowsMixin`, `RejectsMixin`, `_TypeBaseFilter`, `TypeAllowlistFilter` [SOURCE_CODE]
- `meta.py` - Processor that injects a meta TXT record containing time/uuid/version/provider/extra.. Key: `_keys`, `MetaProcessor`, `get_time`, `get_uuid`, `values` [SOURCE_CODE]
- `ownership.py` - Processor that injects TXT ownership records and filters plan changes to only owned records.. Key: `OwnershipProcessor`, `process_source_zone`, `_is_ownership`, `process_plan` [SOURCE_CODE]
- `restrict.py` - Processor that restricts record TTLs to configured min/max or an allowed set.. Key: `RestrictionException`, `TtlRestrictionFilter`, `process_source_zone` [SOURCE_CODE]
- `spf.py` - Validates SPF TXT records by checking DNS lookup limits and deprecated mechanisms.. Key: `SpfDnsLookupProcessor`, `process_source_zone`, `_get_spf_from_txt_values`, `_process_answer`, `_check_dns_lookups` [SOURCE_CODE]
- `templating.py` - Processor that applies Python .format-style templating to record values using context vars.. Key: `TemplatingError`, `Templating`, `process_source_and_target_zones` [SOURCE_CODE]
- `trailing_dots.py` - Processor that ensures DNS record targets/values end with '.' where required.. Key: `_no_trailing_dot`, `_ensure_trailing_dots`, `EnsureTrailingDots`, `process_source_zone` [SOURCE_CODE]

## octodns/provider/

- `__init__.py` - Provider exception hierarchy for octoDNS provider integrations.. Key: `ProviderException`, `SupportsException` [SOURCE_CODE]
- `base.py` - BaseProvider implements shared provider planning workflow and provider capability filtering. Key: `BaseProvider`, `__init__`, `_process_desired_zone`, `_process_existing_zone`, `_include_change` [SOURCE_CODE]
- `plan.py` - Implements Plan safety checks and renderers for JSON/Markdown/HTML/log outputs.. Key: `Plan`, `Plan.raise_if_unsafe`, `Plan.data`, `TooMuchChange`, `RootNsChange` [SOURCE_CODE]
- `yaml.py` - Loads/writes DNS records from YAML files, optionally split per zone/record.. Key: `YamlProvider`, `_apply`, `populate`, `_populate_from_file`, `_split_sources` [SOURCE_CODE]

## octodns/record/

- `__init__.py` - Re-exports public record/value classes for the octodns.record package.. Key: `ARecord`, `RecordException`, `ValidationError`, `Record`, `ValueMixin` [SOURCE_CODE]
- `a.py` - Defines IPv4 'A' record value parsing/validation via Ipv4Value.. Key: `Ipv4Value`, `ARecord`, `Record.register_type(ARecord)` [SOURCE_CODE]
- `aaaa.py` - Defines IPv6 'AAAA' record value parsing/validation via Ipv6Value.. Key: `Ipv6Value`, `AaaaRecord`, `Record.register_type(AaaaRecord)` [SOURCE_CODE]
- `alias.py` - Implements ALIAS record type with root/non-root validation rules.. Key: `AliasValue`, `AliasRecord`, `AliasRecord.validate`, `Record.register_type(AliasRecord)` [SOURCE_CODE]
- `base.py` - Core DNS Record factory/validation plus shared mixins for value(s) handling.. Key: `unquote`, `Record`, `Record.register_type`, `Record.registered_types`, `Record.new` [SOURCE_CODE]
- `caa.py` - Defines CAA record value parsing, validation, and template support. Key: `CaaValue.parse_rdata_text`, `CaaValue.validate`, `CaaValue.template`, `CaaRecord`, `Record.register_type(CaaRecord)` [SOURCE_CODE]
- `change.py` - Represents create/update/delete changes between DNS record states. Key: `Change`, `Change.record`, `Create.data`, `Update.data`, `Delete.data` [SOURCE_CODE]
- `chunked.py` - Chunking + validation helpers for TXT-like record values.. Key: `_ChunkedValuesMixin`, `chunked_value`, `chunked_values`, `rr_values`, `_ChunkedValue` [SOURCE_CODE]
- `cname.py` - Implements CNAME record type with root CNAME restriction.. Key: `CnameValue`, `CnameRecord`, `CnameRecord.validate`, `Record.register_type(CnameRecord)` [SOURCE_CODE]
- `dname.py` - Implements DNAME record type using target-value semantics.. Key: `DnameValue`, `DnameRecord`, `Record.register_type(DnameRecord)` [SOURCE_CODE]
- `ds.py` - Defines DS record value parsing, deprecated-field handling, and validation. Key: `DsValue.parse_rdata_text`, `DsValue.validate`, `DsValue.__init__`, `DsValue.template`, `DsRecord` [SOURCE_CODE]
- `dynamic.py` - Provides dynamic (geo/subnet) rule/pool support for records.. Key: `_DynamicPool`, `_DynamicRule`, `_Dynamic`, `_DynamicMixin`, `_DynamicPool.__init__` [SOURCE_CODE]
- `exception.py` - Defines record validation exception with human-readable reasons.. Key: `RecordException`, `ValidationError`, `ValidationError.build_message`, `ValidationError.__init__` [SOURCE_CODE]
- `geo.py` - Implements legacy GeoDNS record support with validation and update diffing. Key: `GeoCodes.validate`, `GeoCodes.parse`, `GeoValue._validate_geo`, `GeoValue.parents`, `_GeoMixin.validate` [SOURCE_CODE]
- `https.py` - HTTPS record type as an extension of the generic SVCB record model. Key: `HttpsValue`, `HttpsRecord`, `Record.register_type(HttpsRecord)` [SOURCE_CODE]
- `ip.py` - Base support for IP-valued DNS record fields with normalization. Key: `_IpValue.parse_rdata_text`, `_IpValue.validate`, `_IpValue.process`, `_IpValue.__new__`, `_IpAddress` [SOURCE_CODE]
- `loc.py` - Defines LOC record value parsing, validation, and rdata formatting. Key: `LocValue.parse_rdata_text`, `LocValue.validate`, `LocValue.__init__`, `LocValue.rdata_text`, `LocRecord` [SOURCE_CODE]
- `mx.py` - Defines MX record value parsing, validation, templating, and record registration.. Key: `MxValue`, `MxRecord`, `Record.register_type` [SOURCE_CODE]
- `naptr.py` - Implements NAPTR record value parsing/validation/rendering and templating.. Key: `NaptrValue`, `parse_rdata_text`, `validate`, `process`, `rdata_text` [SOURCE_CODE]
- `ns.py` - Defines NS record/value types for octoDNS.. Key: `NsValue`, `NsRecord`, `Record.register_type(NsRecord)` [SOURCE_CODE]
- `openpgpkey.py` - Defines OPENPGPKEY record value handling for base64 key material. Key: `OpenpgpkeyValue.parse_rdata_text`, `OpenpgpkeyValue.validate`, `OpenpgpkeyValue.process`, `OpenpgpkeyValue.template`, `OpenpgpkeyRecord` [SOURCE_CODE]
- `ptr.py` - Defines PTR record/value types, with backward-compatible single-value access.. Key: `PtrValue`, `PtrRecord`, `value`, `Record.register_type(PtrRecord)` [SOURCE_CODE]
- `rr.py` - Provides RFC-style Rdata container and parse error type for RR records.. Key: `RrParseError`, `Rr` [SOURCE_CODE]
- `spf.py` - Defines deprecated SPF record type backed by chunked values.. Key: `SpfRecord`, `Record.register_type(SpfRecord)` [SOURCE_CODE]
- `srv.py` - Implements SRV record value parsing/validation and SRV target templating.. Key: `SrvValue`, `parse_rdata_text`, `validate`, `template`, `SrvRecord` [SOURCE_CODE]
- `sshfp.py` - Defines SSHFP record value parsing, validation, and templating. Key: `SshfpValue.parse_rdata_text`, `SshfpValue.validate`, `SshfpValue.template`, `SshfpRecord`, `Record.register_type(SshfpRecord)` [SOURCE_CODE]
- `subnet.py` - Validates and parses subnet strings using ipaddress.. Key: `Subnets.validate`, `Subnets.parse` [SOURCE_CODE]
- `svcb.py` - Implements RFC9460 SVCB value parsing/validation/serialization and record registration.. Key: `validate_svcparam_port`, `validate_svcparam_alpn`, `validate_svcparam_iphint`, `validate_svcparam_mandatory`, `validate_svcparam_ech` [SOURCE_CODE]
- `target.py` - Centralizes FQDN validation and templating for record target fields.. Key: `validate_target_fqdn`, `_TargetValue`, `_TargetsValue` [SOURCE_CODE]
- `tlsa.py` - Defines TLSA record value parsing, validation, and templating. Key: `TlsaValue.parse_rdata_text`, `TlsaValue.validate`, `TlsaValue.template`, `TlsaRecord`, `Record.register_type(TlsaRecord)` [SOURCE_CODE]
- `txt.py` - Defines TXT record/value types backed by chunked values.. Key: `TxtValue`, `TxtRecord`, `Record.register_type(TxtRecord)` [SOURCE_CODE]
- `uri.py` - Defines URI record value parsing, validation, and templating with IDNA. Key: `UriValue.parse_rdata_text`, `UriValue.validate`, `UriValue.__init__`, `UriValue.template`, `UriRecord.validate` [SOURCE_CODE]
- `urlfwd.py` - Implements URLFWD record value parsing, validation, templating, and equality.. Key: `UrlfwdValue`, `UrlfwdValue.parse_rdata_text`, `UrlfwdValue.validate`, `UrlfwdRecord`, `Record.register_type(UrlfwdRecord)` [SOURCE_CODE]

## octodns/secret/

- `__init__.py` - Secrets package initializer [SOURCE_CODE]
- `base.py` - Base class for secret providers with consistent logging and naming.. Key: `BaseSecrets`, `BaseSecrets.__init__` [SOURCE_CODE]
- `environ.py` - Fetches secret values from environment variables with optional VAR/DEFAULT parsing.. Key: `EnvironSecretsException`, `EnvironSecrets`, `fetch` [SOURCE_CODE]
- `exception.py` - Defines the base exception type for the secrets subsystem. Key: `SecretsException` [SOURCE_CODE]

## octodns/source/

- `__init__.py` - DNS source package initializer [SOURCE_CODE]
- `base.py` - Abstract base class for octoDNS sources providing populate() and support checks. Key: `BaseSource.__init__`, `BaseSource.populate`, `BaseSource.supports`, `BaseSource.SUPPORTS_DYNAMIC`, `BaseSource.__repr__` [SOURCE_CODE]
- `envvar.py` - Source that injects environment variables into TXT records at runtime.. Key: `EnvironmentVariableNotFoundException`, `EnvVarSourceException`, `EnvVarSource`, `EnvVarSource._read_variable`, `EnvVarSource.populate` [SOURCE_CODE]
- `tinydns.py` - Imports TinyDNS zone files into octoDNS records.. Key: `_unique`, `TinyDnsBaseSource`, `SYMBOL_MAP`, `TinyDnsBaseSource.populate`, `TinyDnsFileSource` [SOURCE_CODE]

## tests/

- `helpers.py` - Test helpers: dummy sources/providers/processors and utilities.. Key: `TemporaryDirectory`, `CountingProcessor`, `DummySecrets`, `PlannableProvider`, `SimpleProvider / GeoProvider / DynamicProvider` [TEST]
- `test_octodns_equality.py` - Unit tests for EqualityTupleMixin comparison semantics. Key: `TestEqualityTupleMixin`, `test_basics`, `test_not_implemented` [TEST]
- `test_octodns_idna.py` - Unit tests for IDNA encoding/decoding utilities and IdnaDict behavior.. Key: `TestIdna`, `TestIdnaDict` [TEST]
- `test_octodns_plan.py` - Unit tests covering Plan safety checks, serialization, and renderer output formats.. Key: `TestPlanSortsChanges`, `TestPlanLogger`, `TestPlanHtml`, `TestPlanJson`, `TestPlanMarkdown` [TEST]
- `test_octodns_processor_acme.py` - Tests AcmeManagingProcessor ownership/selection logic for _acme-challenge records.. Key: `TestAcmeManagingProcessor` [TEST]
- `test_octodns_processor_clamp.py` - Unit tests covering TTL clamping behavior and invalid configuration handling.. Key: `TestClampProcessor`, `test_processor_min`, `test_processor_max`, `test_processor_maxmin`, `test_processor_minmax` [TEST]
- `test_octodns_processor_meta.py` - Unit tests for MetaProcessor value rendering, up-to-date detection, and plan suppression.. Key: `TestMetaProcessor`, `test_args_and_values`, `test_is_up_to_date_meta`, `test_process_plan` [TEST]
- `test_octodns_processor_ownership.py` - Tests OwnershipProcessor source-zone ownership TXT generation and plan filtering semantics.. Key: `TestOwnershipProcessor`, `test_process_source_zone`, `test_process_plan`, `test_remove_last_change`, `test_should_replace` [TEST]
- `test_octodns_processor_restrict.py` - Unit tests for TTL restriction processor and restriction exception behavior. Key: `TestTtlRestrictionFilter`, `TtlRestrictionFilter`, `RestrictionException` [TEST]
- `test_octodns_processor_spf.py` - Unit tests for SPF DNS lookup processor expanding includes and enforcing constraints. Key: `TestSpfDnsLookupProcessor`, `SpfDnsLookupProcessor._get_spf_from_txt_values`, `SpfDnsLookupProcessor.process_source_zone`, `SpfDnsLookupException`, `SpfValueException` [TEST]
- `test_octodns_processor_templating.py` - Unit tests validating templating substitutions, trailing dot handling, context injection, and errors.. Key: `TemplatingTest`, `CustomValue`, `Single`, `Multiple`, `_find` [TEST]
- `test_octodns_processor_trailing_dots.py` - Tests EnsureTrailingDots processor for multiple DNS record types.. Key: `EnsureTrailingDotsTest` [TEST]
- `test_octodns_record_a.py` - Unit tests for A record behavior: values, equality, changes, and IPv4 validation. Key: `TestRecordA`, `test_a_and_record`, `test_validation_and_values_mixin` [TEST]
- `test_octodns_record_aaaa.py` - Unit tests for AAAA record parsing, normalization, and validation. Key: `TestRecordAaaa`, `assertMultipleValues`, `test_aaaa`, `test_validation`, `test_more_validation` [TEST]
- `test_octodns_record_alias.py` - Unit tests for ALIAS record behavior: value lowering, validation, and changes. Key: `TestRecordAlias`, `test_alias`, `test_alias_lowering_value`, `test_validation_and_value_mixin`, `test_template_validation` [TEST]
- `test_octodns_record_caa.py` - Unit tests for CAA record/value parsing, comparison, and validation.. Key: `TestRecordCaa`, `TestCaaValue` [TEST]
- `test_octodns_record_change.py` - Unit tests for ordering of DNS record changes. Key: `TestChanges`, `test_sort_same_change_type`, `test_sort_same_different_type` [TEST]
- `test_octodns_record_chunked.py` - Tests chunked TXT/SPF parsing, validation, boundary splitting, and templating.. Key: `TestRecordChunked`, `TestChunkedValue`, `SmallerChunkedMixin` [TEST]
- `test_octodns_record_cname.py` - Unit tests for CNAME record behavior, validation, and templating checks. Key: `TestRecordCname`, `assertSingleValue`, `test_validation`, `test_template_validation` [TEST]
- `test_octodns_record_dname.py` - Unit tests for DNAME record behavior, validation, and templating checks. Key: `TestRecordDname`, `assertSingleValue`, `test_validation`, `test_template_validation` [TEST]
- `test_octodns_record_ds.py` - Unit tests for DS record value parsing, comparison, validation, and templating. Key: `TestRecordDs`, `test_ds`, `TestDsValue`, `test_template` [TEST]
- `test_octodns_record_geo.py` - Unit tests for GEO A/geo codes and GeoValue validation/comparison. Key: `TestRecordGeo`, `TestRecordGeoCodes`, `test_geo`, `test_validate`, `test_geo_value` [TEST]
- `test_octodns_record_ip.py` - Unit tests for IPv4/IpValue parsing-noop and template no-op. Key: `TestRecordIp`, `TestIpValue` [TEST]
- `test_octodns_record_loc.py` - Unit tests for LOC record/value parsing, validation, and ordering.. Key: `TestRecordLoc`, `TestLocValue` [TEST]
- `test_octodns_record_naptr.py` - Unit tests for NAPTR record/value parsing, validation, equality, ordering, and templating.. Key: `TestRecordNaptr`, `test_naptr`, `test_naptr_value_rdata_text`, `test_validation`, `test_flags_case_insensitive` [TEST]
- `test_octodns_record_ns.py` - Unit tests for NS record behavior, validation, and templating checks. Key: `TestRecordNs`, `test_ns`, `test_ns_value_rdata_text`, `test_validation`, `test_template_validation` [TEST]
- `test_octodns_record_openpgpkey.py` - Unit tests for OPENPGPKEY record parsing, validation, changes, and templating. Key: `TestRecordOpenpgpkey`, `test_openpgpkey_value_rdata_text`, `test_validation`, `TestOpenpgpkeyValue` [TEST]
- `test_octodns_record_ptr.py` - Unit tests for PTR record behavior, validation, and templating checks. Key: `TestRecordPtr`, `test_ptr_lowering_value`, `test_ptr`, `test_ptr_rdata_text`, `test_template_validation` [TEST]
- `test_octodns_record_spf.py` - Unit tests for SPF record parsing and validation. Key: `TestRecordSpf`, `assertMultipleValues`, `test_spf`, `test_validation` [TEST]
- `test_octodns_record_srv.py` - Unit tests for SRV record/value parsing, validation, equality, and templating.. Key: `TestRecordSrv`, `TestSrvValue`, `test_srv`, `test_srv_value_rdata_text`, `test_valiation` [TEST]
- `test_octodns_record_sshfp.py` - Unit tests for SSHFP record parsing, validation, diffing, and templating. Key: `TestRecordSshfp`, `test_sshfp`, `test_sshfp_value_rdata_text`, `TestSshFpValue`, `test_validation` [TEST]
- `test_octodns_record_target.py` - Unit tests for generic target value parsing and templating placeholders. Key: `TestRecordTarget`, `TestTargetValue`, `TestTargetsValue` [TEST]
- `test_octodns_record_tlsa.py` - Unit tests for TLSA record parsing, validation, and change detection. Key: `TestRecordTlsa`, `TestTlsaValue`, `test_tlsa`, `test_tsla_value_rdata_text`, `test_validation` [TEST]
- `test_octodns_record_txt.py` - Unit tests for TXT record parsing, chunking, and RDATA formatting. Key: `TestRecordTxt`, `assertMultipleValues`, `test_long_value_chunking`, `test_rr` [TEST]
- `test_octodns_record_uri.py` - Unit tests for URI record parsing, validation, diffing, and templating. Key: `TestRecordUri`, `test_uri`, `test_uri_value_rdata_text`, `TestUriValue`, `test_valiation` [TEST]
- `test_octodns_record_urlfwd.py` - Unit tests for URLFWD record parsing, validation, diffing, and templating. Key: `TestRecordUrlfwd`, `test_urlfwd`, `test_validation`, `test_urlfwd_value_rdata_text`, `TestUrlfwdValue` [TEST]
- `test_octodns_secret_environ.py` - Unit tests for EnvironSecrets.fetch: env lookup, default parsing, coercion, and errors.. Key: `TestEnvironSecrets`, `test_environ_secrets` [TEST]
- `test_octodns_source_envvar.py` - Unit tests for environment-variable based source populating zones. Key: `TestEnvVarSource`, `test_read_variable`, `test_populate` [TEST]
- `test_octodns_source_tinydns.py` - Unit tests for TinyDNS file source parsing into records. Key: `TestTinyDnsFileSource`, `test_populate_normal`, `test_populate_normal_sub1`, `test_populate_normal_sub2`, `test_populate_in_addr_arpa` [TEST]
- `test_octodns_yaml.py` - Unit tests for octodns.yaml safe_load/safe_dump: ordering, include, and merge behavior. Key: `TestYaml`, `test_stuff`, `test_include`, `test_include_merge`, `test_order_mode` [TEST]

## tests/config/

- `alias-zone-loop.yaml` - Fixture config testing alias chains and alias loops in zones [CONFIG]
- `always-dry-run.yaml` - Fixture config toggling always-dry-run per zone [CONFIG]
- `bad-plan-output-config.yaml` - Fixture config with invalid plan_outputs provider settings [CONFIG]
- `bad-plan-output-missing-class.yaml` - Invalid config fixture missing plan output class [TEST]
- `bad-provider-class-module.yaml` - Invalid provider config with non-existent module path [TEST]
- `bad-provider-class-no-module.yaml` - Invalid provider config with class name lacking module prefix [TEST]
- `bad-provider-class.yaml` - Invalid provider config with non-existent module/class package [TEST]
- `dump-processors.yaml` - Fixture config using processors (allowlist and unknown processor) during dump [CONFIG]
- `dynamic-arpa-no-normal-source.yaml` - Fixture config for auto-arpa without a normal input source [CONFIG]
- `dynamic-arpa.yaml` - Fixture config for auto-arpa population with normal source present [CONFIG]
- `dynamic-config-no-list-zones.yaml` - Test config for dynamic zones when provider cannot list_zones [CONFIG]
- `dynamic-config.yaml` - Fixture config exercising dynamic/empty config fields and processor keys [CONFIG]
- `dynamic.tests.yaml` - Fixture config covering dynamic pools, rules, weights, and fallbacks [DATA]
- `empty.yaml` - Empty YAML fixture for base config parsing tests [TEST]
- `missing-provider-class.yaml` - Invalid provider config missing provider class attribute [TEST]
- `missing-provider-config.yaml` - Provider entry missing required configuration fields [TEST]
- `missing-provider-env.yaml` - Test config referencing a non-existent provider environment directory [CONFIG]
- `missing-sources.yaml` - Invalid config fixture with zones missing sources [TEST]
- `no-dump.yaml` - Test config where the dump target is written to /tmp/foo [CONFIG]
- `plan-output-filehandle.yaml` - Test config for manager plan_outputs using a provider class key [CONFIG]
- `processors-missing-class.yaml` - Test config validating missing/invalid processor class definitions [CONFIG]
- `processors-wants-config.yaml` - Test config where a processor requires config params but none provided [CONFIG]
- `processors.yaml` - Test config exercising global and per-zone processors [CONFIG]
- `provider-problems.yaml` - Test config validating provider source/target resolution errors [CONFIG]
- `secrets.yaml` - Fixture config for secret handlers and handler ordering constraints [CONFIG]
- `simple-alias-zone.yaml` - Test config verifying zone aliasing behavior [CONFIG]
- `simple-arpa.yaml` - Test config for auto-generating ARPA zones (IPv4/IPv6 PTR) [CONFIG]
- `simple-split.yaml` - Test config for SplitYamlProvider writing multiple files [CONFIG]
- `simple-validate.yaml` - Test config validating basic zone processing across multiple providers [CONFIG]
- `simple.yaml` - Baseline test config for processing zones from sources to dump targets [CONFIG]
- `sub.txt.unit.tests.yaml` - Empty unit-test fixture for text subconfiguration. [TEST]
- `subzone.unit.tests.yaml` - Fixture defining a subzone with A records for unit tests. [TEST]
- `unit.tests.yaml` - Large fixture defining unit.tests DNS records and special name variants [DATA]
- `unknown-processor.yaml` - Test config referencing a missing processor name for validation behavior [CONFIG]
- `unknown-provider.yaml` - Test config referencing an unknown source in a zone [CONFIG]
- `unknown-source-zone.yaml` - Test config with an alias zone pointing at a missing zone [CONFIG]
- `unordered.yaml` - Fixture verifying YAML key order independence for DNS records. [TEST]
- `zone-threshold.yaml` - Zone config fixture defining update/delete percentage thresholds [CONFIG]

## tests/config-semis/

- `escaped.semis.yaml` - Fixture YAML testing escaped semicolons in TXT values [TEST]
- `unescaped.semis.yaml` - Fixture YAML testing unescaped semicolons in TXT values [TEST]

## tests/config/dynamic-arpa/

- `3.2.2.in-addr.arpa.yaml` - Empty YAML fixture for dynamic in-addr.arpa test case [TEST]
- `b.e.f.f.f.d.1.8.f.2.6.0.1.2.e.0.0.5.0.4.4.6.0.1.0.6.2.ip6.arpa.yaml` - Empty YAML fixture for dynamic ip6.arpa test case [TEST]
- `unit.tests.yaml` - Fixture YAML for dynamic ARPA/PTR generation tests [CONFIG]

## tests/config/hybrid/

- `one.test.yaml` - Hybrid config fixture enabling flat zone file TXT processing. [TEST]

## tests/config/hybrid/two.test./

- `$two.test.yaml` - Hybrid test fixture for a root-level TXT record. [TEST]
- `split-zone-file.yaml` - Hybrid test fixture defining TXT record from split zone file. [TEST]

## tests/config/include/

- `array.yaml` - Fixture for including an array value via YAML loader. [TEST]
- `dict.yaml` - Simple include fixture providing a small mapping [TEST]
- `dict_too.yaml` - Fixture YAML used to validate !include loading order and parent merge [TEST]
- `empty.yaml` - Empty YAML fixture used for include tests. [TEST]
- `include-array-with-dict.yaml` - Fixture to test including multiple YAML items into an array [TEST]
- `include-array-with-non-existant.yaml` - Fixture to test error handling for missing included YAML [TEST]
- `include-array-with-unsupported.yaml` - Fixture to test rejecting unsupported include inputs [TEST]
- `include-dict-with-array.yaml` - Fixture to test including multiple items into a dict value [TEST]
- `include-doesnt-exist.yaml` - Fixture expecting failure when YAML include target is missing. [TEST]
- `main.yaml` - Fixture YAML exercising !include array/dict/nested/subdir includes [TEST]
- `merge.yaml` - Fixture to test YAML merge keys with included dicts [TEST]
- `nested.yaml` - Fixture for nested YAML includes using !include in subdirectories. [TEST]

## tests/config/include/subdir/

- `value.yaml` - Included YAML fixture providing a simple string payload. [TEST]

## tests/config/override/

- `dynamic.tests.yaml` - Fixture YAML overriding dynamic test record values [CONFIG]

## tests/config/split/

- `shared.yaml` - Fixture for shared-zone file content gated by split processing. [TEST]
- `unit.tests.yaml` - Fixture for unit-test split zone file TXT content. [TEST]

## tests/config/split/dynamic.tests.tst/

- `a.yaml` - Test fixture for dynamic weighted geolocation A records. [TEST]
- `aaaa.yaml` - Test fixture for dynamic weighted geolocation AAAA records. [TEST]
- `cname.yaml` - Test fixture for dynamic weighted geolocation CNAME records. [TEST]
- `real-ish-a.yaml` - Test fixture for dynamic A records with AWS-like regions and weights. [TEST]
- `simple-weighted.yaml` - Test fixture for simple single-pool weighted dynamic CNAME. [TEST]

## tests/config/split/subzone.unit.tests.tst/

- `12.yaml` - Fixture for an A record named '12' in subzone test config split [TEST]
- `2.yaml` - Fixture for an A record named '2' in subzone test config split [TEST]
- `test.yaml` - Fixture for an A record named 'test' in subzone test config split [TEST]

## tests/config/split/unit.tests.tst/

- `$unit.tests.yaml` - Fixture containing per-type DNS record definitions for unit tests. [TEST]
- `_srv._tcp.yaml` - Fixture for SRV record unit tests. [TEST]
- `aaaa.yaml` - Fixture for an AAAA record in unit tests config split [TEST]
- `cname.yaml` - Fixture for a CNAME record in unit tests config split [TEST]
- `dname.yaml` - Fixture for a DNAME record in unit tests config split [TEST]
- `excluded.yaml` - Fixture marking a record as excluded via octodns settings [TEST]
- `ignored.yaml` - Fixture marking a record as ignored via octodns settings [TEST]
- `included.yaml` - Fixture marking a record as included for a specific test scope [TEST]
- `mx.yaml` - Fixture for MX record unit tests. [TEST]
- `naptr.yaml` - Fixture for NAPTR record unit tests. [TEST]
- `ptr.yaml` - Fixture for a PTR record with multiple values in unit tests config split [TEST]
- `spf.yaml` - Fixture for an SPF TXT record in unit tests config split [TEST]
- `sub.yaml` - Fixture for an NS record with two values in unit tests config split [TEST]
- `txt.yaml` - Fixture for TXT record unit tests. [TEST]
- `urlfwd.yaml` - Fixture for URLFWD records with split behavior in unit tests [TEST]
- `www.sub.yaml` - Fixture for an A record 'www.sub' in nested split configuration [TEST]
- `www.yaml` - Fixture for an A record 'www' in unit tests config split [TEST]

## tests/config/split/unordered.tst/

- `abc.yaml` - Fixture for an A record used to test unordered split loading [TEST]
- `xyz.yaml` - YAML fixture defining an 'xyz' A record for split/unordered test [TEST]


---
*This knowledge base was extracted by [Codeset](https://codeset.ai) and is available via `python .codex/docs/get_context.py <file_or_folder>`*
