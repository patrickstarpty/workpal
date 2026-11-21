# API client resource wrappers — bounded static audit

Root review pending. No backend support, runtime behavior or whole-client closure is asserted.

Scope: `packages/core/api/client.ts:3022–4055`, from listAgentTasksPage through revokePersonalAccessToken. uploadFile at 4058 is excluded. JSON preserves all 110 declarations and 109 request anchors, with exact bodies to expose every local branch and parsing argument. Only the assigned three artifacts were written.

The shared execution proof and adjacent core/agents-cloud batches have matching current source hashes. Shared fetch/fetchRaw, credentials, unauthorized handling, error parsing, workspaceHeader and parseWithFallback behavior are reused only within their documented scope. publishPluginPackage uses global fetch, captures credentials, builds multipart locally, handles 401, parses errors and JSON; the existing execution proof covers its direct fetch layer.

Local effects include URLSearchParams, encoding, JSON serialization, FormData append, array accumulation, response projections and throws. Response json/arrayBuffer/blob consume the existing response; they do not initiate another endpoint. Theme package converts bytes to Uint8Array; screenshot returns Blob. No caller callback is invoked in this range; AbortSignals are passed into transport.

listIssueUnread requests successive cursor pages, appends parsed items, stops on null or immediately repeated cursor. It has no fixed page bound and does not detect longer cursor cycles. listAgentTasksPage reads the next-cursor header. Working-agent filters choose mine/relation before parent. Plugin installation list suppresses ApiError 404 only. previewPlugin passes readOnly true. listSkills chooses removeDefault/null for strict validation and throws on null; ordinary mode uses the empty fallback. Archive import catches transport errors for remapping, then consumes JSON and invokes skillFromImportResult. No installation commands execute during this audit.

Exact remaining gaps: archivedInboxQuery invoked by archivedInboxParams; remapSkillImportError and skillFromImportResult invoked by importSkillArchive. These are own invoked helpers, not external boundaries. Individual schema implementations are outside the range; Zod schema methods and native response methods are explicit boundaries. setPluginEnabled has enable/disable branches but the copied inventory tuple maps enable only. callPluginAction uses request.method and arbitrary request.path; the GET/context inventory candidate is retained separately and excluded from exact inventory arrays because it cannot represent the invoked dynamic method. Its optional context issue query and optional JSON body are local branches. No neighboring candidate is substituted.

JSON validation checks file hashes, snapshot hashes, exact source spans, request anchors and copied inventory tuples. Tests and runtime/network/model calls were not run. Shared inventory and ledgers remain untouched.

## Root review checkpoint

Validated every recorded declaration against current source lines and every copied tuple against inventory. Independently reviewed import error/result helpers (local parsing only) and archived query builder. Nested date/filter helper evidence and schema proof reconciliation remain; no whole-client closure.
