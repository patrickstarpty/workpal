# Transport proof pointer reconciliation

Root review pending. Pointer reconciliation only; no whole-application/backend completion claim.

All 48 input sources have one disjoint outcome: {'missing': 42, 'resolved': 6}.

Expected hashes below come from existing artifact records; current hashes are byte comparisons, not new prior-review evidence. Original review scope remains unchanged.

## apps/web/proxy.ts

Outcome: missing. Current SHA-256: `2a25fa333d06a4ffc4a460194e1b0206ebec6ecbf1a5bb65a7cf927d43037a81`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/analytics/exception-dedupe.ts

Outcome: missing. Current SHA-256: `5f48cbc3bb9cbcc64f3753b126602299e86dec008add952b6dbdbc5c48aa7242`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/analytics/index.ts

Outcome: missing. Current SHA-256: `c8f89eb97ee538a3168787f873702d35bea36696a50cfebf6014faebfb01538a`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/api/schemas.ts

Outcome: resolved. Current SHA-256: `f75704eeb37705c0f72b4bd89ff89e848289f3fe7cee154b9bed7ff280be674d`.

- `server/contracts/batches/api-client-section-reconciliation.json#/source_hash_checks/258/expected` expected `f75704eeb37705c0f72b4bd89ff89e848289f3fe7cee154b9bed7ff280be674d`; matches current: True.
- `server/contracts/batches/api-client-section-reconciliation.json#/source_hash_checks/274/expected` expected `f75704eeb37705c0f72b4bd89ff89e848289f3fe7cee154b9bed7ff280be674d`; matches current: True.
- `server/contracts/batches/api-client-section-reconciliation.json#/source_hash_checks/277/expected` expected `f75704eeb37705c0f72b4bd89ff89e848289f3fe7cee154b9bed7ff280be674d`; matches current: True.
- `server/contracts/batches/api-client-section-reconciliation.json#/schema_proof_reuse/checks/0/expected` expected `f75704eeb37705c0f72b4bd89ff89e848289f3fe7cee154b9bed7ff280be674d`; matches current: True.
- `server/contracts/batches/api-client-wrappers-agents-cloud.json#/root_helper_review/sources/1/sha256` expected `f75704eeb37705c0f72b4bd89ff89e848289f3fe7cee154b9bed7ff280be674d`; matches current: True.
- `server/contracts/batches/api-client-wrappers-attachments-chat.json#/proofs/1/source_hash_checks/1/expected` expected `f75704eeb37705c0f72b4bd89ff89e848289f3fe7cee154b9bed7ff280be674d`; matches current: True.
- `server/contracts/batches/api-client-wrappers-attachments-chat.json#/proofs/2/source_hash_checks/0/expected` expected `f75704eeb37705c0f72b4bd89ff89e848289f3fe7cee154b9bed7ff280be674d`; matches current: True.
- `server/contracts/batches/api-client-wrappers-tail.json#/proof_reuse/1/checked_source_hashes/1/sha256` expected `f75704eeb37705c0f72b4bd89ff89e848289f3fe7cee154b9bed7ff280be674d`; matches current: True.
- `server/contracts/batches/api-client-wrappers-tail.json#/proof_reuse/2/checked_source_hashes/0/sha256` expected `f75704eeb37705c0f72b4bd89ff89e848289f3fe7cee154b9bed7ff280be674d`; matches current: True.
- `server/contracts/batches/local-source-dispositions.json#/sources/6/sha256` expected `f75704eeb37705c0f72b4bd89ff89e848289f3fe7cee154b9bed7ff280be674d`; matches current: True.
- `server/contracts/batches/platform-session-transport-coverage.json#/files/5/sha256` expected `f75704eeb37705c0f72b4bd89ff89e848289f3fe7cee154b9bed7ff280be674d`; matches current: True.
- `server/contracts/batches/schema-callback-transport-coverage.json#/source/sha256` expected `f75704eeb37705c0f72b4bd89ff89e848289f3fe7cee154b9bed7ff280be674d`; matches current: True.
- `server/contracts/batches/schema-data-transport-coverage.json#/files/1/sha256` expected `f75704eeb37705c0f72b4bd89ff89e848289f3fe7cee154b9bed7ff280be674d`; matches current: True.

## packages/core/auth/index.ts

Outcome: resolved. Current SHA-256: `d58b7c88eb046c4a8f85a304e53df1e772accc6b8b5962e1d9cd82e8d17daffe`.

- `server/contracts/batches/surface-local-helper-closure.json#/root_adapter_review/sources/3/sha256` expected `d58b7c88eb046c4a8f85a304e53df1e772accc6b8b5962e1d9cd82e8d17daffe`; matches current: True.

## packages/core/auth/store.ts

Outcome: resolved. Current SHA-256: `bdf848809606d29488ffb8135f88db3e0c55f22ebb93c2d6dc92b97442b6aaae`.

- `server/contracts/batches/platform-session-transport-coverage.json#/files/6/sha256` expected `bdf848809606d29488ffb8135f88db3e0c55f22ebb93c2d6dc92b97442b6aaae`; matches current: True.

## packages/core/auth/utils.ts

Outcome: missing. Current SHA-256: `4e5587980441adb106f4c1390438d3f23fcc0a7c03cccba57947d99917b98e4c`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/onboarding/index.ts

Outcome: missing. Current SHA-256: `c1f6e1281127843d82927653ca480249f0717c618c8c893043f7d4b6398ca9eb`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/onboarding/mika.ts

Outcome: missing. Current SHA-256: `d37207c1bdb6af4aa38df73b6250be87938d0f5033915d8d89c892a6d4c3f345`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/onboarding/needs-backfill.ts

Outcome: missing. Current SHA-256: `f4ea2dd21d59bf71eed2bcbb18d44d4a1ca02e0df7e1d4ea79125b913e82eb06`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/onboarding/queries.ts

Outcome: missing. Current SHA-256: `2c15cadd1e4a4009117c642ca33a24e498a6b2489cff15b4d4faa78ba063e81d`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/onboarding/step-order.ts

Outcome: missing. Current SHA-256: `b4479f657ceaa50ac5969ffb66389842ea05c9c9b5b05f51c0e04f176b5b1763`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/onboarding/store.ts

Outcome: missing. Current SHA-256: `58b4710ed8fe681e0d9fceaea864877450506fed625d9e323ea64812e6bcdb01`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/onboarding/types.ts

Outcome: missing. Current SHA-256: `d6567cfdac15799f0591b44f7ff25e4211f946480f5091d792525b000413e3d5`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/onboarding/use-bootstrap-mika.ts

Outcome: missing. Current SHA-256: `b3e61f9a1ef5562ee25c77b1cb9ace96d74bb29c18c50d46213b3f093eff8880`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/search-index/client.ts

Outcome: missing. Current SHA-256: `a132891a806e86cb621174ee5b7673622a3ff1030c3faf45ab4ddfda3971fa3b`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/search-index/engine.ts

Outcome: missing. Current SHA-256: `49843f4a5a7cf59499ffc731a20d47837a59d6eb6fe3c2ba78c824e7612d5547`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/search-index/hooks.ts

Outcome: missing. Current SHA-256: `dbe0ee29db23e4e343e28b21a9d5f2928a89c9ff5e24741d3ffe3c7c47a1ed3f`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/search-index/host.ts

Outcome: missing. Current SHA-256: `1247835ab771a916e1fd212a291874422aba3a7d0bdfd78fc0887699dcc79697`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/search-index/index.ts

Outcome: missing. Current SHA-256: `fc1491b72c5715ab8ac7fe595951a8c070a2deba9848327907eb5f3acd5bd5cd`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/search-index/instance.ts

Outcome: missing. Current SHA-256: `1c77f39d03a439f438b085e68da08e02e4ec4c0ee9d348f7d1b84174eec41f76`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/search-index/protocol.ts

Outcome: missing. Current SHA-256: `afb4d520260ce4f0de2aaf1b86fe7eb5dcb7c477764674d83d4f686b2b383352`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/search-index/store.ts

Outcome: missing. Current SHA-256: `8f09399e799150bebf51bc17a56cbcd71a99d397216665e16d7309988660e317`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/search-index/sync.ts

Outcome: missing. Current SHA-256: `ad270abfe82ed00f068aa081274f067e450a303c3d0e44cc7e462ff1fed70036`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/search-index/testing.ts

Outcome: missing. Current SHA-256: `4d5ddfbb7f7ca48c48b26e36182694e5a91b05c1ad4c4027fb4a82a6189ff0d6`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/search-index/worker.ts

Outcome: missing. Current SHA-256: `a0efdaab79e904a84e77521c9c6f8e95085a63c0360db4bc8e87b2a923481587`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/workspace/avatar-url.ts

Outcome: resolved. Current SHA-256: `293b4ea5130a2abe9112f33c6452464b8eceae119d49883ce4c7fbbdc16d84e7`.

- `server/contracts/batches/avatar-foreground-transport-coverage.json#/files/7/sha256` expected `293b4ea5130a2abe9112f33c6452464b8eceae119d49883ce4c7fbbdc16d84e7`; matches current: True.
- `server/contracts/batches/dashboard-surface-transport-coverage.json#/files/15/sha256` expected `293b4ea5130a2abe9112f33c6452464b8eceae119d49883ce4c7fbbdc16d84e7`; matches current: True.

## packages/core/workspace/hooks.ts

Outcome: resolved. Current SHA-256: `7531c31b1caa51b0254eff7738c3ed14cd831a467c311d9aa8cce3ddff2964d3`.

- `server/contracts/batches/api-client-section-reconciliation.json#/source_hash_checks/196/expected` expected `7531c31b1caa51b0254eff7738c3ed14cd831a467c311d9aa8cce3ddff2964d3`; matches current: True.
- `server/contracts/batches/api-client-section-reconciliation.json#/source_hash_checks/241/expected` expected `7531c31b1caa51b0254eff7738c3ed14cd831a467c311d9aa8cce3ddff2964d3`; matches current: True.
- `server/contracts/batches/api-client-wrappers-core.json#/reused_proofs/1/semantic_facts/files/8/sha256` expected `7531c31b1caa51b0254eff7738c3ed14cd831a467c311d9aa8cce3ddff2964d3`; matches current: True.
- `server/contracts/batches/api-client-wrappers-core.json#/reused_proofs/2/semantic_facts/files/8/sha256` expected `7531c31b1caa51b0254eff7738c3ed14cd831a467c311d9aa8cce3ddff2964d3`; matches current: True.
- `server/contracts/batches/create-issue-transport-coverage.json#/files/8/sha256` expected `7531c31b1caa51b0254eff7738c3ed14cd831a467c311d9aa8cce3ddff2964d3`; matches current: True.
- `server/contracts/batches/dashboard-surface-transport-coverage.json#/files/9/sha256` expected `7531c31b1caa51b0254eff7738c3ed14cd831a467c311d9aa8cce3ddff2964d3`; matches current: True.
- `server/contracts/batches/inline-run-transport-coverage.json#/files/4/sha256` expected `7531c31b1caa51b0254eff7738c3ed14cd831a467c311d9aa8cce3ddff2964d3`; matches current: True.
- `server/contracts/batches/issue-detail-edit-section.json#/reused_evidence/1/source_hash_checks/8/sha256` expected `7531c31b1caa51b0254eff7738c3ed14cd831a467c311d9aa8cce3ddff2964d3`; matches current: True.
- `server/contracts/batches/issue-detail-edit-section.json#/reused_evidence/2/source_hash_checks/4/sha256` expected `7531c31b1caa51b0254eff7738c3ed14cd831a467c311d9aa8cce3ddff2964d3`; matches current: True.
- `server/contracts/batches/issue-detail-query-section.json#/files/4/sha256` expected `7531c31b1caa51b0254eff7738c3ed14cd831a467c311d9aa8cce3ddff2964d3`; matches current: True.
- `server/contracts/batches/issue-detail-render-section.json#/root_resolver_sources/2/sha256` expected `7531c31b1caa51b0254eff7738c3ed14cd831a467c311d9aa8cce3ddff2964d3`; matches current: True.
- `server/contracts/batches/issue-mutations-transport-coverage.json#/files/8/sha256` expected `7531c31b1caa51b0254eff7738c3ed14cd831a467c311d9aa8cce3ddff2964d3`; matches current: True.
- `server/contracts/batches/issue-surface-controller-closure.json#/reused_evidence/2/validated_sources/8/sha256` expected `7531c31b1caa51b0254eff7738c3ed14cd831a467c311d9aa8cce3ddff2964d3`; matches current: True.
- `server/contracts/batches/surface-local-helper-closure.json#/reused_support/source_hash_checks/5/sha256` expected `7531c31b1caa51b0254eff7738c3ed14cd831a467c311d9aa8cce3ddff2964d3`; matches current: True.
- `server/contracts/batches/swimlane-transport-coverage.json#/root_supporting_sources/7/sha256` expected `7531c31b1caa51b0254eff7738c3ed14cd831a467c311d9aa8cce3ddff2964d3`; matches current: True.

## packages/core/workspace/index.ts

Outcome: missing. Current SHA-256: `caf88cf4a54d9a8ea522b81ea12fc5513697acd0eb620d2e5d2837e34cbd41cb`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/workspace/mutations.ts

Outcome: missing. Current SHA-256: `adda48f2f085d43f47bad8324aec43a6a7ab3ce33e3900f52fc06e2945a07665`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/workspace/pending-delete.ts

Outcome: missing. Current SHA-256: `f078428d74d68e05d95ef785b766b1095e571bc3a2839c3d3878ff2e0a58f511`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/workspace/sort-workspaces.ts

Outcome: missing. Current SHA-256: `874c4c332e18ca9cacdfd131ccb00d14af797835fb45fc5d3b453f3ce7a2d02e`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/core/workspace/workspace-url.ts

Outcome: missing. Current SHA-256: `677079fbc96fc385c53963d8df46e4885d3a2d8f311363366871246a5c22e457`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/views/editor/attachment.tsx

Outcome: missing. Current SHA-256: `ef13ff980fbd2466ceac8853dd161738906280f506d065d30799f6c6adad922e`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/views/editor/paste-as-file.ts

Outcome: missing. Current SHA-256: `2718abe4f5e36b1d5e5b5618e9d89b9d7abca24ff42439ef4d754c2e13bed5f7`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/views/editor/preview-sequence-context.tsx

Outcome: missing. Current SHA-256: `c7321ab6181aa9ac65a6b0822175b55a3d979a43204cfb9a337ad68a17117efe`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/views/editor/use-composer-submit.ts

Outcome: missing. Current SHA-256: `17c5930a144fc9ffda4a27c213c247f87b9ab404d5bcc785ce8c7039bc7780a0`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/views/editor/use-editor-upload.ts

Outcome: resolved. Current SHA-256: `577b4d53238fb342b44c63108a72c89e16c80b22e90fa0823dbcf3614f37c7c8`.

- `server/contracts/batches/creation-dialog-transport-coverage.json#/files/6/sha256` expected `577b4d53238fb342b44c63108a72c89e16c80b22e90fa0823dbcf3614f37c7c8`; matches current: True.
- `server/contracts/batches/editor-extension-transport-coverage.json#/files/7/sha256` expected `577b4d53238fb342b44c63108a72c89e16c80b22e90fa0823dbcf3614f37c7c8`; matches current: True.
- `server/contracts/batches/issue-detail-edit-section.json#/reused_evidence/2/source_hash_checks/9/sha256` expected `577b4d53238fb342b44c63108a72c89e16c80b22e90fa0823dbcf3614f37c7c8`; matches current: True.
- `server/contracts/batches/issue-detail-query-section.json#/files/9/sha256` expected `577b4d53238fb342b44c63108a72c89e16c80b22e90fa0823dbcf3614f37c7c8`; matches current: True.
- `server/contracts/batches/issue-detail-query-section.json#/remaining_helper_reconciliation/sources/5/sha256` expected `577b4d53238fb342b44c63108a72c89e16c80b22e90fa0823dbcf3614f37c7c8`; matches current: True.
- `server/contracts/batches/issue-detail-render-section.json#/root_upload_sources/0/sha256` expected `577b4d53238fb342b44c63108a72c89e16c80b22e90fa0823dbcf3614f37c7c8`; matches current: True.

## packages/views/plugins/surface-bridge.ts

Outcome: missing. Current SHA-256: `550c96b4caa8c2443410b45eec25e94a9fe9e97421f657dfa5201f973d4e035a`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/views/runtimes/components/update-section.tsx

Outcome: missing. Current SHA-256: `b08c679773b22d6ebab5aa584bcfd0c5780db58861e18d119a9fe69512954ef1`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/views/voice/dialog-footer.tsx

Outcome: missing. Current SHA-256: `1798cf676bf866cc7ef39b9c446d52cb80576f687988964bb66ae88252e136cb`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/views/voice/engine.ts

Outcome: missing. Current SHA-256: `52cca1f87b9464a3ff2a82bb8a75645fa8f4c39400eddd2bf411b9ef3997ebcb`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/views/voice/index.ts

Outcome: missing. Current SHA-256: `3222686bd470113c026d46a8eaac2ab713fe3d2e3feb4c9899885ecde719565b`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/views/voice/recorder.ts

Outcome: missing. Current SHA-256: `64ae8632ec512772d829d1baf1baa1a76915e14c8e24d61a4b515ce52d31e0b0`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/views/voice/use-composer-voice.ts

Outcome: missing. Current SHA-256: `99ff79ebf5b20b1c16578d53f6cb4d0dbcb2810c9c6b765fa6cd6caf016d9aaf`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/views/voice/voice-models.tsx

Outcome: missing. Current SHA-256: `628d910862da7590ca2e04fc60853c86b5a6993c7fca661c7d3f9b287bc1d793`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/views/voice/voice-ui.tsx

Outcome: missing. Current SHA-256: `3d086337ec3ab30be5e62d5a39e1390a41761f12625c1a388012a8b16e830adb`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.

## packages/views/voice/workspace-words.tsx

Outcome: missing. Current SHA-256: `9fc504f68a3f34c3449405d8b5e07143ccaaf635029b887d36683f634fcbc67e`.

No source-associated prior SHA-256 record located in inspected batch JSON artifacts.
