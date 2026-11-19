# Linked workspace review data

The default TAP workspace receives a one-time, additive dataset: three projects, 12 release parents, 80 child tickets, 54 runs, 31 deliveries, 197 commits and 12 release briefs. Six issue states provide active work, review queues, dependencies and completed history. Records are authored fixtures, not actual agent output, measured usage, repository commits or verified test results.

Each child references its release parent and project. Runs capture the ticket requirements and agent profile. Deliveries reference the source run and retain its input snapshot; their manifests list the same commit hashes used in Contribution. Usage records reference finished runs and inherit their ticket's team and project. Release briefs name the child tickets and the blocked dependency. Dates are anchored at first installation and do not move on reload.

The linkedFixtureVersion migration runs only in the default workspace. Existing tickets, review notes and records are retained. Existing contribution imports (including an empty import) are preserved. Legacy authored usage is replaced with linked usage; imported usage is retained. New workspaces stay empty. Fixture fields are metadata and do not add labels to the product interface.

Copilot CLI is the initial harness for all agents and the first choice when creating an agent. A one-time workspace migration updates existing agent profiles on load and fixture snapshots only; historical user-created run snapshots remain intact. Users can subsequently choose another harness. This does not install Copilot CLI, connect a runtime or perform any model calls.

Validation: npm run check passes 61 tests, including reference integrity, contribution totals, review eligibility, idempotence and preservation of imports and notes. Browser QA could not run because @playwright/test is unavailable.


Version 2 replaces the repeated task matrix with 80 domain-specific scenarios of different sizes and project maturity. Commits use deterministic pseudorandom hashes and skewed change sizes; timestamps span six weeks. Selected reviews retain returned first attempts and superseding deliveries. Blocked issues reference open dependencies. The migration removes untouched v1 task chains and retains chains with local changes, discussions, additional runs or review decisions. Counts describe a fresh workspace; retained user work can increase them. All costs, usage, review text and evidence remain authored scenario values, not measurements.

## Dashboard charts and skill library

Analytics now uses TAP's team dashboard composition (chart cards, subtle grid lines, area-backed trends and accessible readouts), with Workpal's neutral surfaces. Contribution shows unique-commit trends, Human / Workpal-assisted share, line-change trends and the six busiest tickets. Usage adds token composition and agent run distribution; Errors includes completed/failed outcomes even in zero-failure periods; Teams shows current status and open workload. Each chart uses the same scoped records as the underlying table. Shared commits are counted once in aggregate trends and under each ticket in the ticket ranking.

Skill Hub adds lifecycle coverage, recorded usage rankings, summary metrics and three featured local skill cards. Eighteen Workpal-owned skill records cover citation audits, uploads, retrieval, conversations, repository onboarding, pipelines, access, releases and skill governance. Agent attachments and authored run skill references are linked to these records. These are local catalog entries, not published repositories or installed executables; no installation commands or fabricated source URLs are offered.

Chart QA covers desktop/mobile bounds, chart rendering, keyboard point navigation and filtered Skill Hub results. The legacy Analytics control suite explicitly uses its dedicated historical usage fixture, separately from linked business scenarios.

## Multica terminology alignment

Analytics exposes Usage, Errors and the explicitly requested Contribution extension. The former Teams tab and Team filter were Workpal additions, not Multica features, and have been removed. Old `tab=teams` / `team=` analytics links normalize to Usage without a hidden department filter. Contribution identifies the ticket's project, not a department presented as a squad. Squads retain their existing leader/member assignment behavior; no inferred membership-based usage attribution or parent-task squad inheritance has been introduced. Existing issue metadata and local review records are preserved.

## Contribution percentages

The primary donut now displays the agent-assisted commit percentage, with Human as the complementary segment. A daily 100% stacked chart uses a fixed percentage axis and shows no rate for days without commits. Project and ticket comparisons use 100% stacked bars with visible percentages and commit denominators; raw commit evidence is available under each ticket. Aggregate and project counts deduplicate repository/SHA pairs. This is Workpal-tagged commit share, including mixed human/agent work, not a measurement of AI-authored code lines. No-data totals show an em dash rather than a fabricated percentage.

## Compact squad contribution view

The requested layout now supersedes the expanded contribution dashboard: one summary ring with period totals, followed by a compact table with one row per existing Squad. Each row shows linked ticket count, unique commits, agent-assisted/human counts, percentage bar and code changes. Squad names open the corresponding existing squad detail.

This Workpal-specific aggregation uses an explicit squad assignee on the ticket, otherwise the nearest ancestor ticket explicitly assigned to a squad. It does not infer ownership from shared agents or project names. Parent traversal handles cycles. Commits are deduplicated per repository/SHA. A commit linked across different squad ownerships is counted only in the overall summary, as are unassigned commits; both counts are stated below the table. Squads with no linked commits remain visible with an unavailable percentage. This is a requested Workpal extension, not a claim about Multica's analytics behavior.

## Theme-aware charts

Chart series now use CSS custom properties shared by SVG marks, ring segments, legends and horizontal bars. Neutral retains all original series colors. Warm uses the existing FWD-inspired orange (#e87722), apricot, amber and terracotta palette; usage stacks, error classes and generated status charts also receive scoped warm colors. No theme preference, data, layout or attribution behavior changes. Browser verification switches Neutral → Warm → Neutral through Settings, checks computed SVG/bar colors (including failure bars) and persistence across Analytics and Skill Hub.
