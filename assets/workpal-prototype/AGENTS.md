# Workpal

Workpal is currently an independent, English-first interactive research prototype for advisor review. It explores AI native SDLC and skill sharing. Actual agent execution and production backends are out of scope for this phase.

- Keep Workpal branding and English UI. Match the current Multica frontend visual system: neutral surfaces, Inter typography, compact rows, restrained borders and shadows. The user explicitly replaced the earlier TAP palette direction.
- Keep prototype, research and simulation labels out of the product interface, as explicitly requested by the user. Describe backend limitations honestly in delivery notes; do not invent real agent responses or measured results.
- Keep the deliverable dependency-free and exportable as one offline HTML file.
- Treat user input as text; escape it before template rendering. Do not execute skill installation commands.
- Changes to prototype interactions should preserve keyboard access, narrow-screen layouts, and local review notes.
- Verify with `npm run check`. Browser interaction tests use Playwright when available; no real model calls.
