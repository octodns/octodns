# octodns documentation

```{include} ../README.md
---
end-before: '## Table of Contents'
---
```

______________________________________________________________________

## User documentation

```{toctree}
:caption: Getting Started:
:maxdepth: 1

examples/basic/README.md
examples/migrating-to-octodns/README.md
records.md
```

```{toctree}
:caption: Guides:
:maxdepth: 1
:glob:

[a-q]*
#records.md
[s-z]*
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

______________________________________________________________________

## Indices and tables

- {ref}`genindex`
- {ref}`modindex`

### Project info

- [License](info/license.md)
- [Changelog](info/changelog.md)
