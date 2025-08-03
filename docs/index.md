# octodns documentation

```{include} ../README.md
---
end-before: '## Table of Contents'
---
```

______________________________________________________________________

## Indices and tables

- {ref}`genindex`
- {ref}`modindex`

### Project info

- [License](info/license.md)
- [Changelog](info/changelog.md)

______________________________________________________________________

## User documentation

```{toctree}
:caption: Guides:
:maxdepth: 1
:glob:

*
```

______________________________________________________________________

## Module documentation

```{toctree}
:caption: Providers:
:maxdepth: 2
:glob:

modules/provider/*
```

```{toctree}
:caption: Sources:
:maxdepth: 2
:glob:

modules/source/*
```

```{toctree}
:caption: Records:
:maxdepth: 2
:glob:

modules/record/*
```

```{toctree}
:caption: Processors:
:maxdepth: 2
:glob:

modules/processor/*
```

```{toctree}
:caption: Other modules:
:titlesonly:
:glob:

modules/*
modules/cmds/*
modules/secret/*
```
