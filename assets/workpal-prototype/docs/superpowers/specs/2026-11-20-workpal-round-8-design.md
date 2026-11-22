# Workpal interaction alignment

Approved direction: implement round 7 in dependency order: shared surfaces, the Issues journey, collections, then navigation and Chat. Preserve Workpal branding, English, local review notes, text escaping and dependency-free offline export. Reference Multica 428ef30fe.

## Approach

Port behavioral contracts into the existing vanilla JavaScript renderer. Reuse the model's workflow transitions and draft persistence. Importing the production React runtime would conflict with the offline dependency constraint; continued cosmetic overrides alone cannot repair interaction behavior.

## Acceptance

Search retains input focus while navigating results; empty input displays actions and recent visits. Property choices anchor to their trigger and restore focus. Workflow changes retain explicit confirmation. Creation focuses title and separates optional details. Verify keyboard, mobile bounds, stored drafts and escaped input. Run npm run check and isolated Playwright; screenshot parity remains separate and unverified until both products use matching data.
