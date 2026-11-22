# Flexible workflow implementation plan

Goal: tickets express outcomes independently of working stage and status. Continue in the existing React/local SQLite app; retain all historical records.

Design: add a new SMART workspace (`workpal-team`) and Workflow work project with 21 authored tickets. Six stages have 3–4 tickets each; seven statuses have three each. Stage is flat issue metadata, never inferred from status or parent. Ticket descriptions record scope, inputs, completion criteria and explicit related work. Include end-to-end and independently scoped work. Overview reads persisted tickets and filters by selected stage or status, with loading/error/empty states. No runtime execution, forced transitions or quantity limits.

- [x] Add coverage for live grouping and independent status/stage values.
- [x] Add insert-only, backed-up registration; prove counts, references and preservation on rerun.
- [x] Replace fixed six-ticket navigation with persisted workflow tickets.
- [x] Run focused tests, npm run check, and browser checks where available. Update handoff.

Ruling: preserve the current dirty workspace because it contains the implementation being continued. Do not merge, delete, reset or move historical tickets. Quantity is initial project content, not a product restriction. New work does not imply implementing a general workflow engine.
