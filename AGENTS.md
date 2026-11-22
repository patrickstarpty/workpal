# Workpal

The active application in `apps/web/` uses the copied Workpal React frontend with a local mock HTTP backend and SQLite in `server/data/`. Top-level structure mirrors Workpal; upstream deployment/CLI sources are retained; apps/docs and apps/storybook retain their upstream implementations; apps/desktop and apps/mobile are empty placeholders, while the default dev/build/check commands target the local mock-backed web app. The prior offline prototype is archived in `assets/workpal-prototype/`; its instructions and historical documents apply to that archive only.

- Keep Workpal branding and English UI, neutral surfaces, Inter typography and the Workpal frontend visual system.
- Keep prototype, research and simulation labels out of the product interface. Describe backend limitations honestly in delivery notes; do not invent agent outputs or measured results.
- Actual model execution and production integrations are out of scope. Unsupported backend operations must fail explicitly.
- Treat user input as text. Do not execute skill installation commands.
- Preserve keyboard access, narrow-screen layouts, SQLite records and archived local review notes.
- Verify active app changes with `npm run check`. Browser tests use Playwright when available; no real model calls.
- The dependency-free single-file export requirement applies to the archived prototype. Verify changes there with `npm run prototype:check`.
