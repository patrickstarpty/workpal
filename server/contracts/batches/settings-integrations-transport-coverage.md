# Settings integrations transport coverage

Static source audit only. Root review pending. No backend support, execution, measured result or global closure claim.

PluginsTab: workspace list/current member identity reads reuse identity proof; installations query enabled only for nonempty wsId. Owner/admin mounts publish/package list and enables management controls. UI role gates do not prove server permission enforcement.

ZIP picker sends first File unchanged as multipart bundle. Client publishPluginPackage uses direct browser fetch with authHeaders, credentials include, handles 401, parses errors/schema; finally clears input. No ZIP unpack or command execution in target.

Review sends version_id; confirm sends preview.version_id and all preview.scopes as granted_scopes. Cancel only clears preview. Delete, enable/disable, uninstall and configure use core mutations. Configuration copies existing values and adds only nonempty newly typed secrets; empty secret does not clear stored value. Number empty/NaN becomes undefined; bool strict true; enum/string remain text.

Plugin mutation onSettled invalidates pluginKeys.all(wsId), including failure. Possible active-query union: installed, packages, surface launch, invocations, MCP tools. Preview has no invalidation. Local publishing/token rotation/manual hook mutation are not target callbacks. Nested activity/MCP panels are separate supporting-component boundaries, not whole-source target claims.

Lark begin on mount and scan-again POSTs agent_id and region encoded with URLSearchParams. Response fields become local session state. Delayed serial poll uses max(2000,pollIntervalSeconds*1000); pending and transient exceptions schedule next timeout. Success invalidates lark installations then toast; error status stops; ApiError 404 session_lost, 401/403 forbidden stop. Cleanup cancels timer/continuation but does not abort in-flight HTTP. No client expiry timer; expiry depends on response, so transient failures can keep polling. Success schedules onClose after 800ms.

QR code is local inline SVG; response qr_code_url is also an unvalidated href opened by user in _blank with noopener noreferrer. No fixed authorization host or ApiClient call ID is invented for browser navigation. Lark installations refetch can poll every 5s while active installation lacks first_message_received_at.

Manual skill submit trims name and description; only name must be nonempty; creates JSON with those fields only, no content/execution. URL submit sends trimmed nonempty text in JSON url; substring source detection affects labels only, not validation or fetching. Browse buttons use fixed https://clawhub.ai, https://skills.sh and https://github.com through openExternal; web opens noopener,noreferrer, desktop bridge is boundary, SSR no-op.

seedAfterCreate sets detail cache locally then invalidates skills and agents prefixes. Possible active union includes skill list/detail/version list/version detail and agent list/detail; no guaranteed request count. refetchType none suppresses refetch after workspace change. Parent onCreated and onClose are opaque callback boundaries.

Folder picker snapshots live FileList before clearing input; generation guards suppress stale discovery. Directory attributes and synchronous click open browser picker. Archive picker wraps original File (size cap only, not extension/content validation). Folder discovery groups shallow SKILL.md roots, excludes ignored paths and binary/oversized supporting entries before reading; selected bytes form STORE ZIP and UTF-8/YAML preview. Limits: entry 1MiB, supporting total 8MiB, supporting count 512, archive 16MiB. Existing archives are not unpacked; reconciliationName null.

Local submit serially prepares selected eligible items and posts multipart file plus on_conflict=fail, pinning X-Workspace-Slug. Workspace id/slug subscription, mounted/cancelled/running guards stop future work; stop does not abort current upload. Response workspace must match owner. Transport/non-ApiError, >=500 and 408 after upload are uncertain and excluded from retry. Check results calls strict listSkills with pinned slug, rejects invalid/mismatched list, invalidates with none and permits retry only for known reconciliationName absent from list. Unknown archive identity stays uncertain.

Standard React/TanStack/browser File/FormData/Blob/TextDecoder/timer/URL semantics, YAML package and UI libraries terminate tracing; no node_modules recursion. RuntimeLocalSkillImportPanel and plugin activity/approval child component internals remain separate scope boundaries; no runtime execution or support claim.

Exact current inventory IDs, methods, path expressions and route objects plus inspected client branch text are in the companion JSON. Supporting modules are separate from the three full target files; whole_source is false for partial client/query reads. Existing plugin-surface, core-query and identity evidence is referenced by hash, not promoted to broader source coverage.


Lark inventory reconciliation: client:5672 GET /api/workspaces/{id}/lark/installations now matches the shared inventory exactly, including path_expression and route. The former missing-ID note is superseded.

Independent review: no unresolved transport edge in the three target callbacks. Child surfaces remain separate scope: RuntimeLocalSkillImportPanel (runtime method), PluginHookActivity (has hooks), PluginScheduleActivity (scheduled hooks), PluginMCPApproval (MCP contributions). Parent onCreated/onClose and desktop openExternal bridge remain opaque callback/platform boundaries. These boundaries do not claim child-source closure.

Validation: all 27 inventory tuples and all recorded source/reused-evidence SHA-256 hashes match current files. Static inspection only; no backend support claim.

Root review accepted bounded target scope. Concrete CreateSkillDialog host: skills-page.tsx:381 onCreated navigates to skill detail; :513 onClose clears local createMethod. These replace the opaque-parent description for the current host; destination mount effects remain a routing boundary. Root verified hashes and exact tuples and spot-checked polling, invalidation and seeding. No runtime tests run.
