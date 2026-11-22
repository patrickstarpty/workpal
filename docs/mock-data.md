# Local review data

`server/mock-content.mjs` authors ticket descriptions and discussions, and generates 90 days of deterministic usage variation when a database is first enriched. These records are fictional review fixtures, not agent executions, measured results, or provider invoices. Analytics costs are calculated by the existing frontend pricing table from fixture token counts.

All six Analytics endpoints aggregate the same SQLite `analytics_runs` records. Records reference existing issues, projects and agents; each carries `fixture_source: authored-review-v1`. Daily and agent totals reconcile; dates respect the requested timezone and period, and deleted issues/projects are excluded. Weekends have less traffic, token/cache ratios vary, and failures include rate limits, timeouts and offline runtimes. No external service is called. Data stays fixed after seeding; as the calendar moves forward older records naturally leave the selected window.

The `rich-mock-v1` migration enriches existing tickets only when descriptions still match the original seed (or are empty). User-edited descriptions and deleted tickets are preserved. Comments and analytics are inserted once. A pre-migration backup of the working database is saved locally as `server/data/workpal-before-rich-mock.sqlite`.

Validation:
- `npm run check`: backend tests and web production build.
- `WORKPAL_PLAYWRIGHT=/path/to/@playwright/test node scripts/mock-data-qa.mjs`: actual ticket descriptions/discussions, four chart metrics, period/project filters, weekly errors, and current-day usage.
- `WORKPAL_PLAYWRIGHT=/path/to/@playwright/test node scripts/web-components-qa.mjs`: existing web navigation/interaction regression checks.

These scripts use an isolated in-memory database and never execute agents. Ticket task runs, pull requests and environments remain empty; the local backend does not fabricate working integrations.

## Contribution

The second Analytics tab ports the archived prototype's contribution summary, commit calendar, per-ticket attribution, and JSON import. It starts with the archived `seed.db.contributionCommits` records, saved once in SQLite under `contribution_data`. Imported records replace that dataset and remain after restarting. Repository + SHA deduplicates summary/calendar totals; multi-ticket commits appear in each ticket row. Explicit Agent/Human counts win; remaining lines follow the Workpal co-author trailer. Date boundaries use the selected timezone. These are authored commit fixtures, not a connected Git service.

`node scripts/contribution-qa.mjs` (with `WORKPAL_PLAYWRIGHT` when necessary) covers tab order, URL restoration, filters, ticket navigation, import/reload, account-menu links and narrow layout. The dev command also starts the documentation app on port 4000 and stops it with the web server. Changelog is available at `/#/review/changelog`; unavailable Discord and Desktop app menu entries are removed.

Avatar images now use the local multipart upload endpoint and SQLite image storage (PNG/JPEG/GIF/WebP, up to 5 MB). Agent avatar selections and image bytes survive restarts; uploads do not use external storage. `scripts/avatar-channels-qa.mjs` verifies emoji selection and cropped-image upload/reload. Legacy channel components remain in source under `Disabled*` exports but are not mounted. Only Microsoft Teams appears in agent/workspace Channels, explicitly unconfigured; no Microsoft authentication or messaging is connected.

Docs language selection uses native disclosure and normal document links, so it works before hydration and preserves the current article across language changes. Route regression tests live in `apps/docs/lib/switch-locale.test.ts`.
