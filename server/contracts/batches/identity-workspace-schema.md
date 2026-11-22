# Bounded identity/workspace schema gate

Status: gaps found. This translates five tables only; schema-map.md remains a raw ledger. JSON lists local persisted columns; grouped decisions below apply to every listed field. No runtime or data changes, PostgreSQL execution, or global completeness claim.

## Representation and defaults

Go UUID IDs become local String primary keys; UUID foreign references become String. Go TIMESTAMPTZ becomes UTC serialized String, including nullable onboarding, pinned, archived and star-prompt timestamps. This is an intentional representation choice, but SQLite does not enforce UUID or timestamp validity. Go gen_random_uuid()/now() defaults become application-supplied IDs/timestamps, not equivalent database defaults. All other fields retain Go nullability unless noted. Local String does not enforce VARCHAR lengths. Nullable fields have no default unless stated.

## User → users

Source base: server/go/migrations/001_init.up.sql:5; Python server/migrations/versions/0002_auth.py:12 and server/src/workpal_backend/auth/models.py:7. id/name/email/avatar_url/created_at/updated_at map directly. email remains unique and required; Python additionally checks lower(trim(email)).

Later persisted fields: onboarded_at (050_add_onboarded_at_to_users.up.sql:1), onboarding_questionnaire (051_add_onboarding_state_to_users.up.sql:1), cloud_waitlist_email/reason (052_add_cloud_waitlist_to_users.up.sql:3), language (060_add_user_language.up.sql:1), profile_description (096_user_profile_description.up.sql:7), timezone (100_user_timezone.up.sql:25), whats_new_seen_version (611_user_whats_new_seen_version.up.sql:4), star_prompt_shown_count/last_shown_at/starred_at (629_user_star_prompt.up.sql:4). These paths are under server/go/migrations/. Questionnaire is required with '{}', description required with '', count required integer with 0; other additions nullable. Waitlist fields are added locally by server/migrations/versions/0011_cloud_waitlist.py:13. Go email VARCHAR(254) and language VARCHAR(20) bounds are not SQLite constraints: require application validation, not a claim of database parity.

Questionnaire intentionally binds UTF-8 BLOB despite migration JSON numeric affinity; this prevents scalar rounding. Decimal decoding/encoding and JSONB text/numeric limits are deliberate (server/src/workpal_backend/auth/json_codec.py:50). Model Text versus migration JSON is not by itself a defect. Legacy numeric scalars are read without rewriting. json_valid is enforced; this is not complete PostgreSQL JSONB equivalence. Waitlist fields persist privately and are explicitly omitted from user responses (same file:67), including nested auth user responses.

Missing: starter_content_state, nullable TEXT (server/go/migrations/054_add_starter_content_state_to_users.up.sql:9; subsequent 095 backfill). Starter-content workflow/import dependencies are incomplete. Do not reintroduce onboarding_current_step (053 removal) or runtime_id/runtime_skipped (098 removal). Their absence is intentional.

## Workspace → workspaces

Base name/slug/description/settings and IDs/times: server/go/migrations/001_init.up.sql:15. context: 006_workspace_context.up.sql:1; repos: 014_workspace_repos.up.sql:1; issue_prefix/counter: 020_issue_number.up.sql:2; avatar_url: 111_workspace_avatar.up.sql:1; attribution_fail_closed: 188_workspace_attribution_fail_closed.up.sql:13 (all under server/go/migrations/). Local declaration: server/src/workpal_backend/workspaces/models.py:3, created through 0003_workspaces.py:9.

slug unique required; settings/repos required JSON with object/array defaults, json_valid local check only (no shape guarantee). counter integer default 0; policy boolean default false represented 0 with boolean check. Prefix required but local lacks Go default ''. Remaining text nullable except name. No missing current workspace columns identified: mcp_config was added in 314 then removed in 318. Counter allocation/attribution execution dependencies require separate behavior verification; stored flags alone do not implement agent execution.

## Member → members

server/go/migrations/001_init.up.sql:26 plus 616_member_pinned.up.sql:1 map all fields; local server/src/workpal_backend/workspaces/models.py:13. Required role check owner/admin/member and workspace/user pair uniqueness retained. pinned_at nullable. Go workspace/user delete CASCADE is absent locally: local FKs use NO ACTION. This is a required delete-semantics decision, not harmless String representation. Go idx_member_workspace (001:176) and idx_member_user_workspace (106_member_user_workspace_index.up.sql:1) lack explicit local counterparts; pair uniqueness covers workspace-leading lookup, not user-leading lookup. Performance gap, not uniqueness gap.

## Invitation → workspace_invitation

server/go/migrations/041_workspace_invitation.up.sql:1 versus server/migrations/versions/0008_workspace_invitations.py:7. Every field maps directly; only invitee_user_id nullable. Role/status checks and pending default retained. Workspace CASCADE and user NO ACTION references retained; three pending partial indexes retained (local invitee-user index has a different name). Go expires_at default now()+7 days is application-supplied locally, with no database default. Pending uniqueness is case sensitive at database level; normalized recipient behavior depends on writers. Email delivery, membership creation, expiry and event atomicity are feature dependencies, not proven by this DDL.

## Issue status → issue_status

server/go/migrations/332_issue_status.up.sql:23 establishes fields and checks; 333/334 add PK, 335 workspace/key unique, 336 active lower(name) unique. 469 consolidation is historical, superseded by 478 expansion and 492 contraction; 493 validates. 490 removes temporary triage-key reservation. 470_issue_status_icon.up.sql:3 adds required icon default ''. Final reconciliation: frozen 0003_workspaces.py:20–27 remains historical (missing icon/defaults, Integer). Final workspaces/models.py:16–33 and 0012_issue_status_constraints.py:9–28 resolve icon, description/is_system/position defaults, Float ordering, key syntax/length, name/description lengths, lowercase hex color, canonical system pairs and system archive checks, and active workspace-scoped ASCII lower(name) uniqueness. 0013_issue_status_no_nul.py:12–32 rejects NUL in every status text column and preserves stored checks, indexes and triggers. Migration paths are under server/migrations/versions/; model under server/src/workpal_backend/.

Open: Unicode case/collation parity with PostgreSQL remains unproven. starter_content_state, member delete cascade parity and member indexing remain open as described above. Local status workspace FK NO ACTION remains stricter than Go's absent FK. Broader Task5/8 catalog, effective-status, archive and other behavior/schema work remains outside this bounded audit. Seven seeded statuses do not prove those workflows.

Exact source-inspected test references (under server/tests/): test_issue_status_schema.py:5 checks icon/FLOAT/check presence; test_issue_status_constraints.py:24 checks invalid INSERT/UPDATE and NUL, :37 system pairs/archive, :52 key/ASCII name uniqueness, :62 archive reuse/defaults/fractions, :72 boundaries/workspace isolation, :79 service seeding. test_issue_status_migration.py:46 verifies historical 0011→head preservation of rows/neighbors, foreign keys and idempotence; :68 verifies invalid legacy upgrade atomicity including data/schema/revision. test_issue_status_nul_upgrade.py:7 verifies historical 0012 NUL failure rollback; :18 verifies 0012→0013 preservation, retained uniqueness, NUL checks and idempotence.

Prior execution evidence from parent review and implementation reports: root independently reported 75 tests passed; agent reported full 571 tests plus 30 subtests and npm run check passed. No tests or npm checks were rerun for this reconciliation. This does not mark the global schema complete or establish executed PostgreSQL equivalence.
