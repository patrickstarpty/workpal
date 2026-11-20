# Environment and investigation records

Enable `workpal.investigation.apps.InvestigationConfig` and apply its migration during integration. Default settings are deliberately unchanged. Dedicated verification settings: `tests.settings_investigation_lane`.

Public Interface (all views are JSON dictionaries):

- `environments.create(actor, project_id, name, timezone, source_refs=())`, `read(actor, environment_id)`, `list_environments(actor, project_id, cursor=0, limit=50)`, `ensure_defaults(actor, project_id, timezone)`, `grant(actor, environment_id, user_id, read, write, publish, revision)`.
- `service.create_service(actor, environment_id, name)`, `read_service(actor, service_id)`, `list_services(actor, environment_id, cursor=0, limit=50)`.
- `sources.create_upload(actor, environment_id, name, allowed_services)`, `read_source(actor, source_id)`.
- `service.start(actor, project_id, environment_id, service_id, problem, key)`, `read(actor, investigation_id)`, `list_investigations(actor, project_id, environment_id=None, cursor=0, limit=50)`.

Each environment is an independent source root. Only its creator initially receives permissions. Workspace owner/admin status alone does not grant access to another environment. Grants require current publish authorization and CAS. Registry grant additionally requires confirmation. Project and supplied source restrictions remain inherited; revocation immediately restricts derived records. Pagination filters authorization failures before counting, and propagates non-403 failures.

Registry actions: environment.create/read/list/ensure_defaults/grant, environment_service.create/read/list, evidence_source.create_upload/read, investigation.start/read/list. Registry writes use existing transactional audit/outbox and durable idempotency. Investigation start also has actor/workspace scoped durable intent identity for direct callers. Problem text is excluded from audit fields. Direct business Interface writes participate in atomic transactions; audit/outbox belongs to Registry invocation, not direct calls.

Upload configuration declares supported text/JSONL source configuration only. It does not accept uploaded contents, connect monitoring, collect logs, consume budgets, produce evidence or findings, identify root causes, call Runtime, or connect Jira. Returned budget 10/window 30 minutes describe defaults only. No UI or default deployment registration is included.

Integration limitations: source_refs currently supported by the Python create Interface only, not environment.create Registry form; optional environment_id filtering is currently supported by Python list_investigations only. Source configuration has no update/delete Interface. Default names are explicitly ensured, never created on read. Production configuration and full application verification remain integration tasks.
