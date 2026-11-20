# Original branch design

Create an independently runnable copy of the local Multica frontend in the Workpal repository on branch `original`. Preserve Workpal branding and English UI. Record the upstream revision and retain applicable licenses.

## Approaches

Recommended: copy the required Multica web frontend and shared packages into this repository, preserving their build system; replace backend integration with a local mock HTTP service backed by SQLite.

Alternative: retain the existing reference wrapper importing the sibling repository. This is smaller but cannot run independently and its fetch interception does not provide database persistence.

## Behavior and scope

Seed SQLite once with explicit fixture records. Frontend reads and supported CRUD operations use the local API; changes survive service restarts. Implement the API contracts needed by the included pages. Unsupported execution and integrations return explicit unavailable responses; never claim real agent execution, authentication, or external integration success.

Keep existing Workpal source, offline export, local review notes and uncommitted work intact. The new app is a separate entry with documented install, development, build and database reset commands. The requested frontend and SQLite service require dependencies and a server; the existing offline export remains available separately.

## Validation

Run npm run check for the existing deliverable, build the copied frontend, and test database persistence and representative API CRUD, including invalid input. Use Playwright if available for frontend loading, edits and reload persistence at desktop and narrow widths.

## Approval

The user approved this structure on 2026-11-20. No real model calls or installation commands contained in skills will be executed.
