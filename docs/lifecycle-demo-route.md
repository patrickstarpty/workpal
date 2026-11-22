> Superseded: the user rejected a fixed one-ticket-per-stage model and a forced single-ticket model. See `docs/handoffs/2026-11-22-ticket-workflow.md`. Do not execute this document as the current plan.

# Workflow team delivery walkthrough

Open http://127.0.0.1:4174 and sign in with `workpal@fwd.com` (local code `888888`). Overview links to the six stages; the parent ticket is `TAP-283`.

1. **TAP-284 · Plan:** accepted scope, Research Analyst review, scope brief v1/v2 and owner acceptance.
2. **TAP-285 · Design:** stable identity decision, Adversarial Reviewer feedback, revised architecture and approval.
3. **TAP-286 · Build:** open the full Execution log to see all four runs. The first attempt fails on a rate limit; attempt 2 succeeds. Code Reviewer finds a leader mapping defect; the revision fixes it. Hover a run and choose View transcript to inspect tool inputs/results and the final summary.
4. **TAP-287 · Test:** QA opens Q-01 for the missing maintenance return link; Maintenance Engineer fixes it. The revised verification report closes the finding.
5. **TAP-288 · Deploy:** Security Engineer reviews the release checklist; the workspace owner approves v2 and rollback ownership. Release Engineer hands off to Reliability Engineer.
6. **TAP-289 · Maintain:** initial review is accepted, but the ticket remains in progress for the next source update. Its handoff returns to Plan.

Activity uses virtual scrolling: use **Jump to latest** to reach the owner decision and handoff. Deliverables group revisions by filename; inspect v2 and use the version selector for v1. Parent Execution log can include child issues.

## Data provenance and limits

These runs, transcripts, review findings, approvals, durations and delivery results are deliberately authored prototype fixtures, not measured or executed agent work. No model or production integration was invoked. Fixture provenance is stored in `_fixture` fields, outside product metadata displays. Original local evidence comments are retained in `archived_evidence_comments`; SQLite is backed up before each seed.

Only the parent and six lifecycle issues are active. The seed `scripts/seed-lifecycle-story.py` refuses a different issue set and reuses stable IDs. Human comments outside its namespace remain intact. Transcript and artifact inspection work locally; starting a new agent run, live retry, production deployment and unsupported operations remain unavailable and fail explicitly.

Reference behavior: https://multica.ai/docs/issues, https://multica.ai/docs/tasks, https://multica.ai/docs/squads and https://github.com/multica-ai/multica (run-lifecycle-demo, squad-demo and deliverables-demo).
