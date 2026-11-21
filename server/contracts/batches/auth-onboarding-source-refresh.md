# Auth/onboarding current source refresh

Review date: 2026-11-21. Finite nine-source review complete; root reviewed finite current-source scope.

Prior dispositions have no prior full-source hashes. Confirmed means statement agrees with current source, not unchanged historical bytes. No historical byte identity or changed-code claim.

All full bodies were independently read in chunks of at most 100 lines; no unread range. Existing dispositions are confirmed against current source. No contradictory semantics identified; this does not establish historical code stability.

## Current full-source evidence

- `packages/core/auth/utils.ts` — lines 1–21; whole_source=true; SHA256 `4e5587980441adb106f4c1390438d3f23fcc0a7c03cccba57947d99917b98e4c`. Pure relative redirect validation; returns text, does not navigate or fetch.
- `packages/core/onboarding/index.ts` — lines 1–33; whole_source=true; SHA256 `c1f6e1281127843d82927653ca480249f0717c618c8c893043f7d4b6398ca9eb`. Reexports store, predicates, queries, bootstrap and constants; no independent transport.
- `packages/core/onboarding/mika.ts` — lines 1–56; whole_source=true; SHA256 `d37207c1bdb6af4aa38df73b6250be87938d0f5033915d8d89c892a6d4c3f345`. Pure system_key and session.last_message predicates; no provisioning occurs here.
- `packages/core/onboarding/needs-backfill.ts` — lines 1–74; whole_source=true; SHA256 `f4ea2dd21d59bf71eed2bcbb18d44d4a1ca02e0df7e1d4ea79125b913e82eb06`. Pure user/dismiss-count predicate; handles legacy string source and array source; no request.
- `packages/core/onboarding/queries.ts` — lines 1–34; whole_source=true; SHA256 `2c15cadd1e4a4009117c642ca33a24e498a6b2489cff15b4d4faa78ba063e81d`. listIssues asks done category, agent/squad assignees, limit 1; reads total. Key under issue prefix permits mutation/realtime refetch; stale 30s; consumer controls enabled.
- `packages/core/onboarding/step-order.ts` — lines 1–13; whole_source=true; SHA256 `b4479f657ceaa50ac5969ffb66389842ea05c9c9b5b05f51c0e04f176b5b1763`. Runtime array of persisted step names only.
- `packages/core/onboarding/store.ts` — lines 1–83; whole_source=true; SHA256 `58b4710ed8fe681e0d9fceaea864877450506fed625d9e323ea64812e6bcdb01`. Questionnaire PATCH then local setUser; conditional nonempty source/role/use-case sends PostHog person properties (buffered before initialization). Completion sends optional body iff completionPath or workspaceId truthy, then refreshMe -> getMe. Waitlist sends interest only; no completion or runtime provisioning.
- `packages/core/onboarding/types.ts` — lines 1–77; whole_source=true; SHA256 `d6567cfdac15799f0591b44f7ff25e4211f946480f5091d792525b000413e3d5`. Type declarations only; no executable runtime source.
- `packages/core/onboarding/use-bootstrap-mika.ts` — lines 1–106; whole_source=true; SHA256 `b3e61f9a1ef5562ee25c77b1cb9ace96d74bb29c18c50d46213b3f093eff8880`. Sequential createMikaAgent with explicit workspaceSlug -> require onboarding_session or throw -> startMikaOnboarding same slug. No fabricated session or runtime response. Success invalidates agent list, chat sessions, messages and paginated messages. Runtime-backed execution/provisioning unsupported for this audit; existing parse fallback started:false is not evidence of execution.

## API edges (accepted proofs reused)

- packages/core/onboarding/queries.ts:24: `listIssues` → `POST /api/issues/query`, `GET /api/issues`; IDs client:1329, client:1344.
- packages/core/onboarding/store.ts:21: `patchOnboarding` → `PATCH /api/me/onboarding`; IDs client:1232.
- packages/core/onboarding/store.ts:61: `markOnboardingComplete` → `POST /api/me/onboarding/complete`; IDs client:1207.
- packages/core/onboarding/store.ts:82: `joinCloudWaitlist` → `POST /api/me/onboarding/cloud-waitlist`; IDs client:1220.
- packages/core/onboarding/use-bootstrap-mika.ts:48: `createMikaAgent` → `POST /api/agents/mika`; IDs client:2103.
- packages/core/onboarding/use-bootstrap-mika.ts:70: `startMikaOnboarding` → `POST /api/chat/sessions/{sessionId}/onboarding`; IDs client:4281.

Completion additionally calls imported refreshMe → getMe, using the existing auth/API proof. No new endpoint is inferred.

## Interface boundary

[
  {
    "source": "packages/core/onboarding/store.ts",
    "interfaces": [
      "api.patchOnboarding",
      "api.markOnboardingComplete",
      "api.joinCloudWaitlist",
      "useAuthStore.getState().setUser",
      "useAuthStore.getState().refreshMe -> getMe",
      "setPersonProperties (external analytics SDK; buffering per accepted proof)"
    ]
  },
  {
    "source": "packages/core/onboarding/queries.ts",
    "interfaces": [
      "queryOptions queryFn (consumer-triggered)",
      "issueKeys.all",
      "api.listIssues"
    ]
  },
  {
    "source": "packages/core/onboarding/use-bootstrap-mika.ts",
    "interfaces": [
      "api.createMikaAgent",
      "api.startMikaOnboarding",
      "useMutation mutationFn/onSuccess",
      "queryClient.invalidateQueries",
      "workspaceKeys.agents",
      "chatKeys.sessions/messages/messagesPage"
    ]
  }
]

bootstrapMika input workspaceSlug/runtimeId/model/title/language
useBootstrapMika workspaceId for invalidation keys
needsSourceBackfill user and dismissCount
memberNeedsMikaSetup agents and member sessions
query consumer enabled/lifecycle; matching active observers determine invalidation refetch

sanitizeNextUrl returns text only: rejects empty, non-single-slash prefix, ASCII 00-1f and backslash; does not decode or navigate
Mika identified by system_key=mika; first matching agent/session; missing or falsy last_message requires setup
backfill requires onboarded user, dismissal count <3, no source or skip; legacy nonempty string counts answered; separate minimum done issue threshold=3
persisted order about_you/workspace/runtime; welcome unpersisted
index reexports only; types declarations only

Reuse identity-workspace-transport-coverage.json and active-web-auth-transport.json for API and active-web callback closure. Invalidations may refetch matching active observers; they are not unconditional requests. No descendant re-audit performed.

## Limits

No runtime/tests/network/model/data/git operations.
No backend support, server idempotency, analytics delivery or actual model execution verified. Source comments describing server behavior are not independent server evidence.
No global/backend completion; root reviewed finite current-source scope.

Root correction: assigned filenames total9, not10. All9 present. Added explicit completion refreshMe GET tuple; current-source evidence does not prove historical byte identity.
