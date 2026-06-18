---
type: minor
---
Add `--honor-lenient` flag to `octodns-validate`; suppress validation warnings for zones and records configured with `lenient: true`, exiting 0 when no non-lenient issues remain. Also fixes a bug where a zone with `lenient: true` in config could cause subsequent zones in the same run to incorrectly inherit lenient mode.
