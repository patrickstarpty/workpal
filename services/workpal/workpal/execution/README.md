# Durable Run admission

Interface: `service.start(actor,subject,agent_id,key,trigger='manual')`,
`read(actor,run_id)`, `control(actor,run_id,operation,revision)` return JSON RunView.
Subject is exactly `{type:'issue',id:<positive integer>}`. Only manual admission and
cancel are implemented. Node identity, retry and resume reject with explicit errors.
Copilot admission is deferred with runtime_unavailable; extension providers reject
with capability_unavailable. No pairing, lease, claim, events, worker or process exists.
Those remain B1b. Completed runs never update Issues or approve human reviews.

All writes use atomic_write with immediate SQLite transactions. A persistent
workspace/actor/start key binds request parameters; conflicts return 409. Replays
recheck current membership and provenance. New keys reuse the unique active
Issue/Agent run. Snapshots contain public Issue/requirements/project/resource/Agent
reads, saved Issue workflow, source roots and a canonical SHA256; real foreign keys
protect saved identities. Resource identifiers are enumerated with a read-only
ProjectResource query because list_resources deliberately filters inaccessible rows;
each resource is then read through its public Interface and denial aborts admission.
A future public unfiltered identifier Interface would remove this enumeration seam.
No foreign-module ORM writes occur.

Read/start/cancel reauthorize current objects. Deferred/queued cancel is immediate;
other active states become cancel_requested, which does not claim process termination.
CAS rejects stale revisions. Terminal cancel preserves state and advances revision.
Registry run.start/read/cancel use existing idempotency, audit and result references;
run.start payload key is the durable business intent, alongside Registry request key.
Reason is always a structured object; non-deferred runs carry an empty code.

Integration must append `workpal.agents.apps.AgentsConfig` and
`workpal.execution.apps.ExecutionConfig`, migrate both apps, and run combined checks.
Only tests.settings_execution_lane currently registers them. No HTTP routes are
needed: existing generic Registry HTTP dispatch supplies the actions after registration.
This module does not make Runtime or the full product operational.

Runtime lease HTTP exposes only POST `/api/runtime/v1/claim` (Runtime bearer)
and POST `/api/runtime/v1/runs/<run_id>/renew` (Task bearer). Both accept closed,
versioned JSON bounded to 16 KiB, bypass CSRF only for these bearer routes, and
return no-store/nosniff responses. Core transactions commit before serialization;
a lost response does not replay a rotated token. Capability verification defaults
to False. No events, logs, stop endpoint, real provider execution, or remote OS
stop guarantee is implemented. HTTP acceptance coverage remains incomplete.
