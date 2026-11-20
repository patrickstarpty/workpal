# Collaboration

Local persisted comments, personal Issue subscriptions and personal Inbox, exposed
only through the generic Registry action HTTP endpoint. No model calls, network calls,
Runtime, Runs, tools or external message dispatch are involved. Text is stored
unchanged; UI escaping belongs to A5. A3 is not complete.

Actions:

- `comment.create {issue_id,body,mention_user_ids?,source_refs?}` requires a key and
  current write permission on the Issue and every supplied source. Body is nonblank,
  at most 20,000 valid UTF-8 characters. Mentions are at most 50 unique positive IDs.
  Archived Issues reject new comments with 409; existing comments and completed
  creation replays remain readable under current source permissions.
- `comment.read {comment_id}` and
  `comment.list {issue_id,cursor?,limit?,include_archived?}` return closed views:
  id, issue_id, author_user_id, body, mentions, revision, archived, created_at,
  updated_at.
- `issue.subscribe`, `issue.unsubscribe`, `issue.subscription.read` accept only
  `{issue_id}` and return `{issue_id,subscribed}`. Writes require a key and current
  read permission. They set only the actor's preference, without changing the Issue.
- `inbox.list {unread_only?,cursor?,limit?}` returns the current recipient's visible
  notifications. It never marks them read. Views contain id, issue_id, comment_id
  (0 when absent), kind, live issue_title, revision, read_at (empty when unread),
  created_at. Titles are projected only after current authorization.
- `inbox.mark_read {notification_id}` and `inbox.mark_unread {notification_id}`
  require a key and expected_revision; current
  source read permission suffices. They change only notification read_at/revision.
  Other recipients' IDs return 404 even for workspace owners.

Lists authorize each row before pagination (default 50, maximum 200); no total or
hidden summary is returned. ActionResult references include each returned row so
Registry audit provenance includes comment-specific restrictions. All writes use
atomic_write; Registry idempotency, business audit and outbox share that transaction.
Ordinary reads do not produce outbox records.

Comment sources always inherit the Issue and append supplied restrictions without
changing Issue provenance. Notification rows hold references and event facts, never
comment text or Issue title. A trusted `notify_comment(actor,persisted_comment)`
function reloads the persisted comment and reuses dynamic authorization inside
the business transaction. Event keys
are derived from comment IDs. Mentions and active subscribers are deduplicated;
mention wins, authors receive no notification. Invalid explicit mentions reject the
whole creation; inaccessible or inactive subscribers are skipped. Other failures
abort the transaction so a retry can deliver the notice. Unsubscribe
preserves historical notifications. Revocation dynamically hides existing records
and blocks read/mark-read replays. No SourceGrant is created by this module.

Subtasks, Activity, Chat and Worker remain unimplemented.

Comment management: `comment.update`, `comment.remove`, and `comment.restore` require an idempotency key and expected revision. The current author or workspace owner/admin must retain write access to both the Issue and Comment sources, including during replay. Remove requires human confirmation and archives the row; restore retains body, mentions and notifications. Lists hide archived comments unless `include_archived` is true; authorized ID reads retain them. Updates preserve omitted fields, clear mentions with `[]`, and only append sources. Only newly added mentions receive revision-scoped notifications; existing notifications inherit appended source restrictions. Registry execution commits business changes, provenance, audit, outbox and replay results together. No external agent execution or notification delivery is performed.

Issue notification hooks: `notify_assignment(actor, issue_id, revision)` and
`notify_blocked(actor, issue_id, revision)` reread persisted Issue state and check
current source write authority and recipient membership/read access. They join the
source write transaction and derive deduplicated event identities internally.
Assignment suppresses human self-notifications; blocked decisions include self.
Notifications inherit Issue provenance, retain references only, and do not dispatch
execution or notify ordinary subscribers. Inbox visibility remains permission-aware.

Custom blocked keys, agent self-assignment, Registry replay/revocation, complete
creation/transition rollback and two-connection SQLite contention are covered by
the service tests. No notice changes the Issue's state or marks another notice read.
