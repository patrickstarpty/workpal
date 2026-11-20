# Uploaded excerpt normalization

`normalize_upload(content: bytes, *, format: str, policy: dict) -> dict` is a pure
Module. It accepts strict UTF-8 text or JSONL, optionally beginning with one BOM.
Input and returned UTF-8 content each have a 2,097,152-byte ceiling. LF records
retain original one-based line numbers; blank lines are skipped, terminal CR is
removed, and only the first 1,000 nonblank records are parsed. Later records
contribute to raw hash and total count, never parsed-field counts.

The closed policy requires version 1 (not boolean), boolean allow_text, and
unique allow_fields/redact_literals lists of at most 100 strings. Field lengths
are 1–128 and literal lengths 1–256 Unicode characters. Fields containing any
redaction literal are rejected. Only exact selected top-level JSON keys survive;
selected values must be scalars. Duplicate keys and nonfinite constants fail.
Finite-number and Unicode validation includes discarded nested values; valid
unselected objects/arrays are still omitted as a whole.
Strings use literal, longest-first, left-to-right, nonoverlapping replacement
with [REDACTED]; replacements are never scanned again. No commands execute.

Content is LF-joined without a trailing LF. JSON uses sorted keys, compact
separators, Unicode output and finite numbers. Policy hashing uses the same
canonical JSON with both lists sorted. raw_sha256 hashes all submitted bytes,
content_sha256 hashes only the returned copy, and policy_sha256 hashes the
canonical policy. Results contain no policy literals or discarded field names.
Counts describe the uploaded excerpt, never an environment's coverage.

DomainError codes are invalid_upload/invalid_redaction_policy (400),
text_upload_not_allowed (403), upload_too_large and
normalized_upload_too_large (413). Generic errors suppress raw exception chains.
The Module prints nothing and writes nothing. Returned lists are fresh.

This implements D1b1 only. Callers must authorize before calling and persist only
the returned copy. Never first store raw logs as Artifact. D1b2 must connect
EvidenceSnapshot, current permissions, transport, idempotency and budgets.
Literal masks are not universal secret detection or permission to publish:
all source/environment restrictions remain. No HTTP, ORM, model calls, time or
deployment inference, diagnosis, measured coverage or production execution is
provided here.

Evidence HTTP accepts bounded octet-stream uploads through active human sessions
with CSRF protection. The dedicated transport reads at most 2 MiB plus one
sentinel byte in memory after target authorization, then rechecks authorization
through submit_upload. It persists only normalized evidence. Read and listing
use current Registry authorization. Uploads describe user supplied excerpts;
unknown event times, deployment identities and ranges remain null. Explicit
ranges are user declarations. Normalization may redact and truncate; it does
not establish complete environment coverage, live collection or model permission.
