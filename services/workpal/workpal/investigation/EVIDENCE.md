# Evidence policy and snapshot storage

This module provides restricted policy management and immutable normalized upload
snapshots through the application Interface. There is no HTTP upload route or
evidence listing Interface yet.

`configure_policy(actor, source_id, policy, expected_revision)` checks current
owner/admin membership, source read/publish and environment write permissions.
Both management interfaces reject executor identities, including executors acting
for an administrator, because policy literals can contain secrets. Upload
execution applies the policy internally without returning its management body.
Registry `evidence_policy.configure` additionally requires human confirmation
and an idempotency key. Its closed payload contains only source_id and policy.
Direct callers are trusted application code; interactive callers use Registry.

New and migrated sources start with current_policy=None and policy_revision=1.
Unconfigured is distinct from a configured policy with an empty allow_fields
list. The first successful CAS creates revision 2. Each subsequent update inserts
an independent version and atomically updates the source pointer and revision.
Input dictionaries are copied. Policy validation and hashing use the public
normalize_upload interface with empty JSONL bytes. Raw upload bytes are never persisted.

`read_policy(actor, source_id)` and Registry `evidence_policy.read` are authorized
management reads requiring the same current permissions. Unconfigured results
contain configured=false, revision=1 and an empty hash, with no policy field.
Configured management results include the policy body. Direct reads do not write;
Registry reads record access audit only and do not create outbox or cache rows.

Ordinary evidence_source.read keeps its existing DTO. Policy literals are absent
from configure results, confirmations, audit fields, outbox and idempotency results.
Confirmation stores only request digest and authorization scope. Saved configure
results still require current permissions before replay. Policy versions are
inserted through this interface and are not overwritten by later configurations.

`submit_upload(actor, investigation_id, source_id, content, *, format, timezone=None,
range_start=None, range_end=None, key)` checks current investigation/source/service
read access and environment write access, then normalizes the input in memory.
Ordinary members may use it when these grants allow. It saves only the normalized
copy, immutable policy identity, hashes, counters, provenance and declared time
metadata. Unknown event/deployment facts remain null. Uploads do not consume the
investigation query budget.

The internal ContextVar capability exists only during submission and is reset on
success or failure. Generic Registry requests cannot manufacture it. Omitted time
values remain null in the persisted intent descriptor; the private Registry wire
uses empty strings for optional form fields. An old key binds the original policy
and resolved timezone. Current permissions are checked again before cached results.
The metadata result and cache omit content; audit fields contain only target IDs
and format. `read_evidence(actor, evidence_id)` uses the read action and returns
metadata plus content under current permissions, with access audit and no outbox.

Explicit aware ISO ranges preserve their original offset strings. Output schemas
use a supported nullable scalar union (`string` or `null`) with the same string
bounds. Snapshot listing, the complete concurrency matrix and HTTP streaming remain
for subsequent tasks.

Task2b listing: `list_evidence` calls the read-only `evidence.list` Registry action.
Current investigation access is checked before scanning. Each candidate rechecks
current source, allowed service, environment and evidence access. Only 403 is
filtered; infrastructure errors propagate. Pagination follows visible IDs, with
limit 1–200 and terminal cursor 0. Snapshot content and policy body are deferred
in the listing projection. Results contain metadata only; Registry records one
access audit and no business outbox or idempotency cache.
HTTP Task3 remains unimplemented. Two-connection upload race acceptance remains
pending; this listing increment does not declare all Task2 acceptance complete.
