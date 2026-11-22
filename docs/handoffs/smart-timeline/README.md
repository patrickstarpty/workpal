# SMART activity chronology repair

User-approved scope: SMART-2, 7, 8, 14, 15 and 20. Organize each ticket's existing authored history by Plan, Design, Build, Test, Deploy and Maintain, using only applicable phases. Give activities coherent timestamps and credible, task-dependent intervals. Do not invent execution evidence.

## Reference and decisions

Read Multica's [Issues](https://multica.ai/docs/issues), [Runs](https://multica.ai/docs/tasks), [Squads](https://multica.ai/docs/squads), and [deliverable demo source](https://github.com/multica-ai/multica/blob/main/apps/docs/components/demos/deliverables-demo.tsx) (blob 08b17ac8c82f459c9be051b828bcc50527801272).

The references establish issue/run separation, retained failed attempts, specific feedback between file versions, and handoff before acceptance. They do not prescribe universal task durations. The chosen intervals are authored scenario timing, not observed measurements or copied production performance.

- SMART-2: backlog design proposal, review questions, prioritization. TDS now originates in the first design deliverable.
- SMART-7: planning, TDS, retained failed attempt, retry, implementation handoff, review and correction request. Missing scoped patch and recheck remain explicit.
- SMART-8: recovery design, TDS, focus/announcement review, requested revision; no invented accepted revision.
- SMART-14: initial TDS now accompanies design progress, before review and the existing v2 work record.
- SMART-15: planning, TDS, implementation, review, revision, verification, decision and handoff. Existing authored decisions are retained; they are not authenticated production acceptance.
- SMART-20: mandatory gates proposal, flexible-entry alternative TDS, review and rejection of mandatory gates. No implementation is implied.

The timeline spans 28–80 minutes per ticket, with distinct task durations and shorter bookkeeping intervals. Task messages fall inside their run envelopes. Review scopes follow design/implementation submissions. Assignment remains intact except for correcting the attributed roles on authored scope/review entries.

## Data safety and limitations

`repair-smart-timeline.py` defaults to a rollback-only preview. `--apply` requires local development authentication, backs up SQLite and writes in one transaction. It guards every modified row by authored fixture provenance or the six existing TDS attachment IDs. Existing record IDs, issue statuses, user activity, actual verification submissions, delivery revisions and document bytes are preserved. Source snapshots and original values remain available.

TDS `created_at` and `uploaded_at` retain the real publication timestamp. `comment_created_at` identifies the earlier authored design activity. These are deliberately distinct; a later attachment import is not a claim that the file was actually uploaded during a historical run. Synthetic work-record attachments follow their producing comments.

The original database backup is `server/data/python/workpal.sqlite.before-timeline-20261122150920855734`. Further backups precede role and phase metadata refinements. `applied.json` and timestamped change reports record the final schedule. `preview.json` records an idempotent rerun with zero changes. The TDS publication manifest and publisher targets were synchronized.

No real model execution, production deployment, new PR, code correction or measured test outcome was generated for the ticket histories. Later real evidence remains at its original time, even when it audits an earlier phase.

## Verification result

`npm run check` exited 0: 9 Node tests, 1,938 Python tests plus 30 subtests, 16 launcher tests, and the production web build passed. Existing warning output is retained in `check.log` (including CSS `::highlight` processing warnings). The data-specific verification confirms all record IDs are retained, unrelated records and actual evidence are unchanged, and TDS checksums/upload times are preserved. The repair dry-run after applying returned zero changes. No browser verification was performed; product UI code was not changed.
