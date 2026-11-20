# Audit and Issue Activity

`service.record` saves Registry access/business events and writes local business
Outbox records for mutating actions in the same transaction. These records are
not execution commands. Idempotent write replay does not create another event.

`activity.list_issue_activity(actor, issue_id, cursor='', limit=50)` returns a
page and its full authorized object/source references. The work module's
`issue.activity.list` adapter exposes the page through Registry. Only explicitly
listed completed Issue and Comment changes enter Activity; reads, subscriptions,
personal Inbox metadata and identity actions are excluded.

The subject must be currently readable. Each event's saved scope and output
references must also be currently readable before it counts toward pagination.
Unavailable events are skipped; service failures propagate. Comment ownership
comes from the collaboration interface, not from incidental source references.
Archive retains authorized history. Each entry contains only its audit ID,
action ID, actor user ID, timestamp and output object references. No request
body, source list or inferred actor execution identity is exposed in the page.

Pages default to 50 entries, with a maximum of 200 and no hidden total. Signed
cursors bind the workspace and Issue and continue ascending `(created_at, id)`
order. Empty string means the beginning or terminal cursor. SQL applies the
cursor boundary; candidate metadata is read in batches without loading request
bodies or caching the whole workspace history. Source checks precede the visible
item limit, so sparse authorization may require scanning multiple batches.

Registry records Activity access with all displayed events' source restrictions,
without writing an Outbox row. Those access records are not themselves shown in
Activity. Direct internal service calls that bypass Registry do not acquire
invented history. No Runtime or external services are used here.
