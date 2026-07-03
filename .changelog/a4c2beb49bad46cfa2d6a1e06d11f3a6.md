---
type: patch
---
Fix MailZoneValidator's single-MX provider exemption to match known providers even when the MX exchange is missing its trailing dot (e.g. when the mx-value-best-practice validator is disabled for a zone)
