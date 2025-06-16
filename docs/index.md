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

### Project infos

- [License](infos/license.md)
- [Changelog](infos/changelog.md)

______________________________________________________________________

## User documentation

```{toctree}
:caption: Guides:
:maxdepth: 1
:glob:

pages/*
```

______________________________________________________________________

## Module documentation

```{toctree}
:caption: Processors:
:maxdepth: 2
:glob:

modules/processor/*
```

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
:caption: Other modules:
:titlesonly:
:glob:

modules/*
modules/cmds/*
modules/secret/*
```
