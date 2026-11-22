> Superseded: the user rejected a fixed one-ticket-per-stage model and a forced single-ticket model. See `docs/handoffs/2026-11-22-ticket-workflow.md`. Do not execute this document as the current plan.

# Lifecycle activity implementation plan

**Goal:** Enrich the existing parent and six lifecycle issues with coherent authored demonstration activity, runs, transcripts, approvals and deliverable revisions.
**Architecture:** Reuse upstream timeline and transcript UI. Store workspace-scoped read-only run/activity/message records in the local backend; generate non-sensitive Markdown deliverables in the web public directory. Seed only the seven existing issues, back up SQLite first, preserve original source records and unrelated data. Synthetic provenance belongs in record metadata and delivery notes.
**Tech stack:** Python, SQLite, FastAPI, React.
**Approved scope:** User confirmed the rich prototype story and explicitly authorized synthetic runs, results, approvals and retries. No model execution or production integrations.

- [ ] Add failing HTTP tests for mixed timeline ordering, run reads, transcripts and workspace isolation.
- [ ] Implement workspace-scoped projections and read-only task detail routes; unsupported mutations remain explicit.
- [ ] Add idempotent fixture generator with six distinct stage narratives, separate failed/retry runs, human approval comments, versioned files and bidirectional handoff links.
- [ ] Update Overview entry copy; verify seven issues only, valid actors/links/timestamps/statuses, deterministic reruns and attachment/transcript contracts.
- [ ] Run targeted tests and npm run check; publish concise route and honest fixture provenance.

Review focus: cross-workspace reads; orphan transcripts; failed attempt overwritten by retry; terminal status disagreeing with final timeline; reseeding duplicating records or overwriting user comments.
