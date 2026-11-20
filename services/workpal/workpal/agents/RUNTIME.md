# Runtime identity core

The six public operations in `runtime_identity` support administrator pairing issuance,
one-time consumption, device authentication, pairing metadata recovery, runtime metadata,
and revision-checked revocation. `RuntimeIdentity` is immutable. Pairing names are fixed
at issuance. Pairing expires after 600 seconds, including the exact expiry instant.

Credentials contain independently generated 32-byte random values with distinct type
prefixes. Only SHA-256 digests are stored. Plain credentials appear only in successful
issuance/consumption return values; there is no replay cache. After a lost consumption
response, an administrator reads pairing metadata, revokes the identified runtime, and
issues a new pairing. Authentication does not impersonate the issuer.

Issuance and consumption record minimal ID facts and outbox entries in their database
transaction. Runtime and pairing references are ordinary derived objects, not permission
roots. Issuance/consumption audit and outbox include their registered object references
and current source scope, with outcome completed. Retryable storage errors retain
their 503 status. Management operations recheck current roles and object permissions. Mutations
require a human administrator; any executor_id other than None is rejected, including
an empty string. Direct revocation has no separate business audit; Registry integration owns that event.

HTTP issuance uses session authentication and CSRF at POST /api/v1/workspaces/<id>/runtime-pairings.
POST /api/runtime/v1/pair alone is CSRF exempt and authenticates only the pairing secret.
Both enforce Host, strict UTF-8 JSON with closed fields, duplicate rejection and a 16 KiB limit;
responses carry no-store and nosniff. Registry exposes runtime.pairing.read, runtime.read and
runtime.revoke with current owner/admin and source checks before replay. Revoke requires
a human actor, revision and idempotency key, without extra confirmation.
There is no Agent binding, lease, event protocol, or real execution. Pairing does not prove provider installation,
authentication, or execution capability.

Validation: the original seven tests plus six independent supervision regressions
and the previous B24 passed (37 total). The review reproduced and fixed an empty
executor bypass, misclassified storage failures, and missing audit object/scope
references. It also checked current grants, inactive/removed issuers and complete
row rollback after actual audit writes. Evidence: /tmp/workpal-b1b1a-review-*.log.

The implementer wrote the original implementation before its tests; a later
process-local NotImplementedError replacement does not count as test-first evidence.
That process deviation remains recorded. The supervisor ran npm run check
successfully (/tmp/workpal-bd-supervision-npm.log); no bypass of protected files
was needed. Binding remains pending.

Task1b1 validation: 7 independent HTTP/Registry tests plus core13 and B24 (44 total).
Real session POST first returned 404; red evidence is in /tmp/workpal-b1b1b-http-red.log.
Suite evidence: /tmp/workpal-b1b1b-http-suite.log. No model or migration changes.

Supervisor HTTP verification added three tests for real CSRF sessions and anonymous
pairing followed by the generic management action endpoints, the exact 16 KiB
boundary, and complete row rollback for revoke after an actual audit write.
HTTP10 plus core13 passed (23 tests), /tmp/workpal-b1b1b-parent.log.
A separate protected prototype source difference is under investigation; this is
not an assertion that the repository-wide integrity gate has passed.

Agent binding management: `bind(actor, agent_id, runtime_id, revision)` and
`unbind(actor, agent_id, revision)` require current human owner/admin membership
and current write access to the Agent, target Runtime, and existing Runtime.
Registry actions `runtime.bind` and `runtime.unbind` require an idempotency key
and the Agent revision. Binding updates increment the Agent revision and the
persistent binding revision; disabled bindings remain available for authorized
replay. Cached replies retain their original revisions, with current write
checks on the saved Agent and Runtime. Unbinding a revoked Runtime is allowed
with current access; it does not establish that a remote process has stopped.
Binding does not enable execution or alter historical Run snapshots. Copilot
remains deferred and extension providers remain unavailable for execution.
