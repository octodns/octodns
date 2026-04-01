# Project Overview

octoDNS manages DNS configuration as code across multiple providers. It loads desired state from YAML, normalizes/validates it into an internal model, populates existing state from a provider backend, computes diffs (create/update/delete), optionally runs processors, and then renders/applies a plan.

Primary usage: command-line tooling + a Python library used by provider/source/processor integrations.

# Key Components

- `octodns/manager.py:Manager` — central orchestrator for config/plugins and end-to-end sync/dump.
- `octodns/provider/base.py:BaseProvider` — base provider lifecycle: populate → desired processing → existing processing → diff → Plan creation.
- `octodns/provider/plan.py:Plan` — plan representation, safety checks, and output rendering.
- `octodns/zone.py:Zone` — zone model, invariants, and diff computation via `Zone.changes()`.
- `octodns/cmds/*:main/entrypoints` — CLI commands (sync/compare/dump/report/validate/versions).
- `octodns/yaml.py:safe_load/safe_dump` — YAML parsing/serialization with `!include` and deterministic key ordering.
- `octodns/record/base.py:Record` — record factory/registry, validation, serialization, IDNA normalization.
- `octodns/idna.py:IdnaDict` — label-wise IDNA normalization and case-insensitive mapping.
- `octodns/processor/base.py:BaseProcessor` — processor hooks and lenient-mode contract.
- `octodns/secret/environ.py:EnvironSecrets` — env-backed config expansion with defaults and int/float coercion.
- Docs build-time link rewriting: `docs/conf.py:_detect_git_ref/_rewrite_repo_local_links`.

# Architecture

```
          ┌──────────────┐
          │   CLI        │
          └──────┬───────┘
                 │
                 v
          ┌──────────────┐
          │   Manager     │
          └──────┬───────┘
                 │ loads config + instantiates plugins
                 v
   ┌───────────────────────────────┐
   │ Providers / Processors / Plans │
   │ populate → normalize → diff     │
   └───────────┬────────────────────┘
               │
               v
        ┌─────────────┐
        │   Zone       │
        │ records/diff │
        └─────┬───────┘
              │
              v
      ┌───────────────────┐
      │ Plan (safety + IO)│
      └─────────┬─────────┘
                │ apply or render
                v
        ┌───────────────┐
        │ Provider backend│
        └───────────────┘
```

# Core Data Structures

- `octodns/zone.py:Zone.records` — `defaultdict(set)` keyed by IDNA-encoded record name; sets represent records at the same node.
- `octodns/zone.py:Zone.changes(existing, desired, provider)` — computes `Create/Update/Delete` changes filtered by provider support and ignored records.
- `octodns/record/base.py:Record.new` — factory selecting concrete record type from the registry; validates and normalizes IDNA.
- `octodns/provider/plan.py:Plan` — holds `changes`, computed counts, `meta`, and `raise_if_unsafe()` safety checks.
- Processor hooks:
  - `octodns/processor/base.py:BaseProcessor.process_source_zone`
  - `octodns/processor/base.py:BaseProcessor.process_target_zone`
  - `octodns/processor/base.py:BaseProcessor.process_source_and_target_zones`
  - `octodns/processor/base.py:BaseProcessor.process_plan`

# Control Flow

1. CLI parses args and config; creates `octodns/manager.py:Manager`.
2. `Manager.sync()` (or `dump/compare/...`) loads zones/providers/processors/plan outputs.
3. For each zone/target:
   - Provider creates/populates `existing` zone.
   - Provider copies `desired` zone and runs normalization hooks.
   - Processors run in two phases (target-side then source+target) with lenient-mode behavior.
   - Diff computed via `Zone.changes()`.
   - `octodns/provider/plan.py:Plan` created (or falsey when no changes and no meta).
   - `Plan.raise_if_unsafe()` enforces safety thresholds including root NS rule.
   - Plan rendered or applied.

# Test-Driven Development

- Before adding new behavior, search for existing tests covering the same construct (often exact exception messages are asserted).
- Prefer running the most focused test module first (examples below).

# Bash Commands

- Run all tests (typical):
  - `pytest -q`
- Run documentation build:
  - `python -m sphinx -b html docs docs/_build/html`
- Run focused suites:
  - Manager: `pytest -q tests/test_octodns_manager.py`
  - Zone: `pytest -q tests/test_octodns_zone.py`
  - Provider base: `pytest -q tests/test_octodns_provider_base.py`
  - Plan/safety/output: `pytest -q tests/test_octodns_plan.py`
  - YAML: `pytest -q tests/test_octodns_yaml.py`
  - Processors (examples):
    - `pytest -q tests/test_octodns_processor_filter.py`
    - `pytest -q tests/test_octodns_processor_meta.py`
    - `pytest -q tests/test_octodns_processor_arpa.py`
    - `pytest -q tests/test_octodns_processor_templating.py`

# Code Style

- Python formatting is configured via Black (`line-length=80`).
- YAML output and ordering are deterministic; tests assert exact output strings.
- Logging uses consistent parameterized style in modified code paths (avoid f-string formatting in log calls).

# Gotchas

- Exact message assertions: many tests compare exception strings and sometimes specific prefixes (e.g. YAML ordering errors).
- Lenient-mode is record-level and hook-level:
  - Processors should use `self.lenient or lenient` when calling zone/record APIs.
  - Some validators skip only when `record.lenient` is true (e.g., TTL restriction).
- IDNA normalization affects keys and eligibility:
  - Use `octodns/idna.py:idna_encode/idna_decode` and `IdnaDict` rather than ad-hoc lowercasing.
- Processor mutation discipline:
  - Processors should not mutate records in-place; use `record.copy()` and `Zone.add_record(..., replace=True)`.
- `octodns/manager.py:_build_kwargs` env expansion is boundary-sensitive:
  - Config uses `env/...` expansion; type coercion is centralized in `octodns/secret/environ.py:EnvironSecrets.fetch`.
- Docs link rewriting is fail-fast and git-dependent:
  - `docs/conf.py:_detect_git_ref()` raises `RuntimeError` if git ref cannot be resolved.

# Pattern Examples

- `octodns/manager.py:Manager._build_kwargs` — builds plugin kwargs from config, including env expansion.
- `octodns/provider/base.py:BaseProvider.plan` — orchestrates populate → processing → diff → Plan.
- `octodns/zone.py:Zone.changes` — central diff computation & filtering.
- `octodns/processor/templating.py:Templating.process_source_and_target_zones` — correct place to apply template rendering (including alias-zone pipeline behavior).

# Common Mistakes

- Breaking processor hook contracts:
  - Don’t return `None` unless documented; plan/sync expects zone/plan objects back.
  - Ensure proper lenient propagation to `record.copy(..., lenient=...)` and `Zone.add_record(..., lenient=...)`.
- Changing plan data/safety contracts:
  - `octodns/provider/plan.py:Plan.data` and root NS unsafe semantics are used by checksum gating and safety tests.
- Changing YAML include/order semantics:
  - `octodns/yaml.py:safe_load` key-order enforcement, `!include` and merge-operator flattening have strict tests.

# Invariants

- Record identity/equality used for diffing is stable and depends on name + RR type (value diffs are separate).
- IDNA keys must be normalized consistently (`Record` + `IdnaDict`).
- Providers must create an `existing` Zone and compute diffs via `Zone.changes()`.
- `Plan.raise_if_unsafe()` must treat root NS changes as unsafe (special-case rule).

# Anti-patterns

- Implementing provider- or record-specific FQDN validation by duplicating logic rather than using:
  - `octodns/record/target.py:validate_target_fqdn`.
- Modifying YAML output formatting/order without updating `octodns/yaml.py` dumper behavior.
- Adding processors that directly mutate `Zone.records`/record internals without using copy/replace.

# [Additional Project-Specific Sections]

## CI / Matrix

I couldn’t reliably extract the workflow matrix in this run (no workflow files were listed by the repository search tool). If you’re changing CI-facing behavior, check `.github/workflows/*` directly in your environment.

## Versioning

- Package version is exposed as both `octodns.__version__` and legacy alias `octodns.__VERSION__`.
- Docs use `octodns.__init__.py:__version__` for Sphinx `release` metadata.

## Docs Build

- Run: `python -m sphinx -b html docs docs/_build/html`
- Note: `docs/conf.py` rewrites repo-local doc links to GitHub URLs using a computed `/tree/<ref>` base. RTD builds prefer `READTHEDOCS_GIT_IDENTIFIER`.

# Verification Checklist

- Run the full test matrix locally or in CI
- Confirm failing test fails before fix, passes after
- Run linters and formatters

# Test Integrity

- NEVER modify existing tests to make your implementation pass
- If a test fails after your change, fix the implementation, not the test
- Only modify tests when explicitly asked to, or when the test itself is demonstrably incorrect

# Suggestions for Thorough Investigation

When working on a task, consider looking beyond the immediate file:
- Test files can reveal expected behavior and edge cases
- Config or constants files may define values the code depends on
- Files that are frequently changed together (coupled files) often share context

# Must-Follow Rules

1. Work in short cycles. In each cycle: choose the single highest-leverage next action, execute it, verify with the strongest available check (tests, typecheck, run, lint, or a minimal repro), then write a brief log entry of what changed + what you'll do next.
2. Prefer the smallest change that can be verified. Keep edits localized, avoid broad formatting churn, and structure work so every change is easy to revert.
3. If you're missing information (requirements, environment behavior, API contracts), do not assume. Instead: inspect code, read docs in-repo, run a targeted experiment, add temporary instrumentation, or create a minimal reproduction to learn the truth quickly.


# Index Files

I have provided an index file to help navigate this codebase:
- `.claude/docs/general_index.md`

The file is organized by directory (## headers), with each file listed as:
`- `filename` - short description. Key: `construct1`, `construct2` [CATEGORY]`

You can grep for directory names, filenames, construct names, or categories (TEST, CLI, PUBLIC_API, GENERATED, SOURCE_CODE) to quickly find relevant files without reading the entire index.

**MANDATORY RULE — NO EXCEPTIONS:** After you read, reference, or consider editing a file or folder, you MUST run:
`python .claude/docs/get_context.py <path>`

This works for **both files and folders**:
- For a file: `python .claude/docs/get_context.py <file_path>`
- For a folder: `python .claude/docs/get_context.py <folder_path>`

This is a hard requirement for EVERY file and folder you touch. Without this, you'll miss recent important information and your edit will likely fail verification. Do not skip this step. Do not assume you already know enough. Do not batch it "for later." Do not skip files even if you have obtained context about a parent directory. Run it immediately after any other action on that path.

The command returns critical context you cannot infer on your own:

**For files:**
- Edit checklist with tests to run, constants to check, and related files
- Historical insights (past bugs, fixes, lessons learned)
- Key constructs defined in the file
- Tests that exercise this file
- Related files and semantic overview
- Common pitfalls

**For folders:**
- Folder role and responsibility in the codebase
- Key files and why they matter
- Cross-cutting behaviors across the subtree
- Distilled insights from every file in that folder

**Workflow (follow this exact order every time):**
1. Identify the file or folder you need to work with.
2. Run `python .claude/docs/get_context.py <path>` and read the output.
3. Only then proceed to read, edit, or reason about it.

If you need to work with multiple paths, run the command for each one before touching any of them.

**Violations:** If you read or edit a file or folder without first running get_context.py on it, you are violating a project-level rule. Stop, run the command, and re-evaluate your changes with the new context.



---
*This knowledge base was extracted by [Codeset](https://codeset.ai) and is available via `python .claude/docs/get_context.py <file_or_folder>`*
