# Developer Agent Guide

Welcome to the octoDNS organization workspace. This guide outlines the project structure, development workflow, and coding guidelines for developers and AI agents.

---

## General Workflow & Guidelines (All Repositories)

This section applies to all repositories under the octoDNS organization (including the core framework and provider/add-on modules).

### Project Structure & Aim

octoDNS is a tool and framework that provides a set of tools and patterns to manage DNS records across multiple providers as code (Infrastructure as Code).

- **Core Repository**: [octodns](https://github.com/octodns/octodns) is the core repository containing the main framework and CLI tools.
- **Provider & Add-on Modules**: Subdirectories/repositories prefixed with `octodns-` (such as [octodns-cloudflare](https://github.com/octodns/octodns-cloudflare), [octodns-route53](https://github.com/octodns/octodns-route53), etc.) are individual modules for integrating different DNS providers or adding specific features.
- **Tooling & Scripts**: All octoDNS repositories follow the GitHub **"Scripts to Rule Them All"** pattern, housing all environment setup, testing, formatting, and other developer tools within the `./script/` directory of each repository.

---

### Development Workflow

Follow this step-by-step workflow when contributing changes:

#### 1. Create a Branch

Always start work by creating a new feature or bugfix branch:

```bash
git checkout -b <branch-name>
```

#### 2. Verify Compliance

Before committing, you must verify your changes comply with the repository standards by running the following scripts from the root of the repository you are modifying:

- **Test Suite**: Run the unit tests.

  ```bash
  ./script/test
  ```

- **Code Coverage**: Verify that code coverage is sufficient (typically 100%).

  ```bash
  ./script/coverage
  ```

  If code coverage is less than 100%, you can use the helper script `./script/coverage-report` to identify the exact files, line number ranges, and branches that are missing coverage:

  ```bash
  ./script/coverage-report
  ```

  > [!TIP]
  > When working in other `octodns-` repos, you can copy or run the `script/coverage-report` utility from the core repository against their generated `coverage.json` file. It outputs parsed information about coverage gaps that is much easier for AI agents and developers to digest and act on than raw JSON/XML reports.

- **Linting**: Ensure code conforms to Python style constraints.

  ```bash
  ./script/lint
  ```

- **Formatting**: Format the code automatically to match repository standards.

  ```bash
  ./script/format
  ```

#### 3. Create a Changelog Entry (First Commit)

The first commit on a branch must contain a changelog entry. Note that you should stage your changes prior to running the changelog command so that they are included in this first commit. Use the changelog tool to create one:

```bash
./script/changelog create --type <type> --commit "Brief description of changes"
```

##### Command Options & Arguments

- **`change-description`** (positional): A short, single-line description of the changes, suitable as an entry in `CHANGELOG.md`. Can include simple markdown formatting and links.
- **`-t, --type {none,patch,minor,major}`**: The scope of the change:
  - `patch`: This is a bug fix.
  - `minor`: Adds new functionality/changes in a fully backwards-compatible way.
  - `major`: Substantial new functionality and/or breaking changes.
  - `none`: This change does not need to be mentioned in the changelog.
- **`-a, --add`**: Run `git add` automatically on the newly created changelog entry.
- **`-c, --commit`**: Run `git commit` to stage and commit the entry (and other staged changes) using the same description.
- **`--continue`**: Continue a previously failed commit attempt.

*Example:*

```bash
./script/changelog create --type patch --add --commit "Fix DNS record parser bug"
```

#### 4. Subsequent Commits

For any subsequent commits on the same branch, use `git commit` normally:

```bash
git commit --message "Commit message"
```

#### 5. Push and Set Upstream

Push your branch to the remote repository and set the upstream branch:

```bash
git push --set-upstream origin <branch-name>
```

#### 6. Create a Pull Request

Use the GitHub CLI (`gh`) to create a pull request:

```bash
gh pr create --title "<title>" --body "<body>" --assignee "@me"
```

##### Common Parameters

- **`-t, --title <string>`**: Title of the pull request.
- **`-b, --body <string>`**: Body description of the pull request.
- **`-d, --draft`**: Mark the pull request as a draft (useful for work-in-progress).
- **`-f, --fill`**: Automatically use the commit title and description.
- **`-a, --assignee login`**: Assign the pull request to people by their login (use `"@me"` to self-assign).

*Example:*

```bash
gh pr create --title "Fix DNS record parser bug" --body "Fixes a bug in the record parser. /cc #123 Fix DNS record parser bug" --assignee "@me"
```

##### PR Guidelines

- **Link related issues & PRs**: Always link related issues and PRs in the description or body using `/cc #NUM REASON` (e.g., `/cc #123 Fix DNS record parser bug`). When issues are fixed or need to be closed by a PR, the mention should use `/cc Fixes #NUM` (e.g., `/cc Fixes #123`). When there are multiple `/cc` links, they should each be on their own line and generally should include a reason for linking them up.
- **Assignee**: Ensure the assignee of the pull request is set to the user (e.g., by using `--assignee "@me"`).

---

## Core Repository Specifics (`octodns/octodns`)

The following guidelines and codebase details are specific to the core `octodns/octodns` repository.

### Repository Structure

The `octodns/octodns` repository contains the core framework and command line tools for managing DNS records as code. Below is a breakdown of the codebase layout:

#### Core Package: `octodns/`

The main Python package is located in [octodns/](octodns/) and contains the following modules:

- [manager.py](octodns/manager.py): The [Manager](octodns/manager.py) class. This is the orchestrator that loads configuration, initializes providers, processes zones, plans changes, and applies updates.
- [zone/](octodns/zone/): Modules related to DNS [Zone](octodns/zone/) loading, representation, validation, and serialization.
- [record/](octodns/record/): Contains the base [Record](octodns/record/) class and individual sub-classes/modules for all supported DNS record types (e.g., A, AAAA, CAA, CNAME, MX, NS, SRV, TXT, etc.).
- [provider/](octodns/provider/): Houses the base [BaseProvider](octodns/provider/) class and built-in/internal providers (like [YamlProvider](octodns/provider/) for reading/writing YAML zone files). External provider modules (such as Cloudflare, Route53, etc.) are hosted in separate repositories.
- [processor/](octodns/processor/): Contains processors that run hook-like transformations or validations on zones/records before the plan or apply phases. Examples include spf, clamp, filter, meta, templating, and ownership processors.
- [source/](octodns/source/): Contains classes for sourcing record data, such as environment variable sources.
- [schema/](octodns/schema/): JSON schemas used to validate configuration files and record syntax.
- [cmds/](octodns/cmds/): CLI commands (e.g. `compare`, `dump`, `report`, `sync`, `validate`).
- [yaml.py](octodns/yaml.py): A custom YAML loader/dumper wrapper that preserves order and handles comments.
- [equality.py](octodns/equality.py): Helper classes/utilities for checking record equality.

#### Tests: `tests/`

The test suite is located in [tests/](tests/) and is organized with files corresponding to their source files (e.g. `test_octodns_manager.py` tests `manager.py`).

#### Development Scripts: `script/`

All development scripts are located in [script/](script/).

---

### Tips & Hints for AI Agents

When working with this core codebase, keep the following details in mind:

#### Strict Code Coverage

The coverage requirements are checked via [script/coverage](script/coverage).

1. **100% Code Coverage**: Your code changes MUST have 100% test coverage (branch coverage is enabled via `--cov-branch`). Any uncovered lines or branches will fail the CI check.
2. **Pragma Limit**: Usage of `# pragma: no cover` is generally limited to handling version compatibilities (see [meta.py](octodns/processor/meta.py#L14-L16) for an example). There is a hard limit check in the script (max 5 allowed in the entire repo). With explicit user approval, it can be used, but the limit check count in [script/coverage](script/coverage) must then be incremented. Otherwise, you must cover your code paths with actual unit tests in [tests/](tests/).

#### Code Style & Formatting

- Code formatting is enforced using `isort` and `black` through [script/format](script/format). Always run `./script/format` on your changes.
- Print statements (`print(...)`) are strictly forbidden in library code (allowed only in commands under `octodns/cmds/`). The [script/lint](script/lint) check enforces this (maximum of 3 print statements allowed globally). Use logging or return values instead.

#### YAML Serialization

- If you modify how YAML files are loaded/written, always use the functions provided in [yaml.py](octodns/yaml.py) to preserve standard formats and ordering, rather than raw `pyyaml` calls.
