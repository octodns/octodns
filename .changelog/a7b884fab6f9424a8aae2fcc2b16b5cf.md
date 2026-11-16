---
type: patch
---
Fix SVCB/HTTPS parsing of svcparam values containing `=` (such as base64 `ech` padding), and stop stripping a quote from values that aren't wrapped in matching quotes
