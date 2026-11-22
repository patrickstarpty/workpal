# Delivery evidence

## Scope and actual behavior
Issue details now include **Delivery evidence** next to Deliverables. Existing tickets with no evidence register show **Evidence pending** even if their historical activity claims success. Original SQLite records are not overwritten. Authored Activity comments receive a read-time pending-evidence notice.

Members can submit full requirements, design, code, test or handoff documents. Code requires diff, findings, fixes and recheck. Tests require method, actual results, failures and uncovered scope. Handoffs require existing exact revision IDs; their contents can be opened inline. Every submission creates an immutable revision, SHA-256 content digest, attachment and Activity comment in one transaction. An optional producing Run must belong to the same ticket and cannot be a marked constructed Run. Human-authored work has no invented Run.

New revisions retain document identity and link their predecessor; stale revisions cannot create branches silently. Reviews record the authenticated member, exact revision, decision, accepted/reviewed scope and remaining issues. A populated form is **not** execution verification and does not automatically mark a ticket accepted. All document text is rendered as text, never executed.

Activity can be located from the register. Real producing Runs use the existing transcript viewer. Attachments use authenticated blob download instead of a bare unauthenticated URL. The register exposes every revision, not just the latest file.

## Review findings and corrections
- Local attachment downloads required workspace authentication: added API blob download with the original filename, covered by a regression test.
- Run IDs alone were insufficient: added the existing transcript action.
- Malformed kind arrays caused a 500: validate type and return 400; regression test covers arrays, objects, null and numbers.
- Reviewer UUID was unclear: resolve the member name and retain its ID.
- Browser selection exposed an ambiguous native select label: added explicit accessible names.

## Verification
- Backend contracts: six evidence tests cover revisions, stale writes, exact-version reviews, authenticated identity, cross-ticket/workspace rejection, structured reports, code/Run/Activity/download linkage, malformed inputs and preservation of old records. The final evidence + workspace-content run passed 34 tests. See [actual output](delivery-evidence/backend-tests.txt).
- UI/download: 21 tests passed. See [actual output](delivery-evidence/ui-tests.txt).
- Playwright: `node scripts/delivery-evidence-qa.mjs` passed on an existing SMART ticket: pending evidence, submission entry, test report fields, and the 390px sidebar entry. It deliberately does not create fake deliverables in the user's database.
- Typecheck remains blocked by three existing unused declarations in `packages/ui/components/common/workpal-graphics.tsx` and `packages/ui/lib/workpal-brand.ts`. No errors remain in the changed evidence files. See [output](delivery-evidence/typecheck.txt).
- Full `npm run check`: Python 1936 passed, 30 subtests passed; Node and launcher checks passed. The build failed on a concurrent change importing nonexistent `useFeatureFlag` in `assignee-picker.tsx`. The import was already removed when inspected; a subsequent `npm run build` passed (exit 0). See [build output](delivery-evidence/build.txt). Full check exit was 1, not a clean pass. See [full output](delivery-evidence/full-check.txt).

## Limits and acceptance
No actual model calls, production integrations, or historical tests were executed by this feature. Existing generated work-record summaries were not promoted into verified evidence. Their claimed development, testing and acceptance still require real source material. Backend contracts and component tests validate submission/review persistence; browser QA does not claim a complete write-and-accept session. No user acceptance decision is recorded for this implementation.
