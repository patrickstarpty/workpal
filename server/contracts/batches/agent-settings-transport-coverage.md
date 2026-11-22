# Agent settings transport source evidence

Status: evidence captured; closure remains pending root review. No runtime or backend support claim.

The JSON follows the core-query files/edges/inventory structure. Four targets have SHA-256 hashes and complete, line-indexed source evidence (semantic_proof array index + 1 is the line number). Supporting modules are separately marked whole_source=false. Client bodies are preserved without shortening conditional branches; inventory entries are copied from frontend-calls.json, retaining existing IDs, methods and path expressions.

AgentAdvancedSettings filters sections by Qoder, OpenClaw, canEdit, MCP support and feature flag. request/confirmDiscard manage local dirty navigation. save forwards agent.id and updates to the detail parent's handleUpdate. EnvTab receives setDirty but no onSaved callback here: no parent refresh may be inferred from its optional notification.

Inspector profile autosave trims name, validates description and permissions, and forwards name/description. Starters require feature support and complete entries. Avatar callbacks forward avatar_url; reuse avatar-foreground evidence for upload and native resources. Runtime/model changes pass through useExecutionControls; runtime changes clear model, thinking and service tier. Thinking/speed and validated concurrency commit use the same owner update. The concrete detail parent optimistically patches list/detail caches, calls updateAgent, caches the response and invalidates the list. Failure restores only mutated fields, invalidates and rethrows.

Activity reads snapshot, infinite task pages and workspace activity through the existing core-query factories. It deduplicates pages by task ID, filters private chat tasks, sorts current/terminal tasks locally and initially displays ten recent entries. Show more reveals twenty cached entries or calls fetchNextPage with cancelRefetch=false only when another page exists and no fetch is in progress; display count advances only without a page error. Issue detail queries are gated by a nonempty issue ID; reuse issue-query evidence. Cancellation guards duplicate clicks, calls cancelTaskById, and relies on realtime invalidation rather than issuing its own refetch. Transcript open/close stores local state; supporting transcript modules are recorded separately.

Environment reveal is explicit, never a mount fetch: getAgentEnv populates entries and baseline. Save rejects unrevealed/duplicate keys, sends custom_env through updateAgentEnv, accepts returned values as baseline, synchronizes bulk text or returns to rows, then optionally calls onSaved. Errors show a toast and finally clears busy state. Row editing, visibility, clipboard parsing, bulk validation and dirty reporting are local. Invalid bulk text blocks Save and counts as unsaved work.

Native clipboard, navigation, focus, timers and dynamic avatar/resource URLs are not invented HTTP endpoints. React, query/virtualization libraries and browser standard libraries remain boundaries.

Outstanding: root must review supporting callback closure and inventory completeness before promoting this evidence to a completed transport closure. Captured source alone is not a claim that every supporting module has been semantically audited.

Concrete callback review

AdvancedSettings general renders AgentDetailInspector with the same onUpdate; save(updates) supplies agent.id. Inspector update(data) likewise supplies agent.id. Detail page lines 227-301 owns handleUpdate: runtime_bound is derived only in optimisticData, while original data is sent to updateAgent. Only written fields are restored on failure; list invalidation is fire-and-forget and error is rethrown.

cacheAgentResponse (workspace/queries.ts:83-104) always sets detail, replaces matching list entry, keeps a cold list cold and, with insertIntoList:false, never appends a missing entry. updateAgent uses PUT /api/agents/${id}, JSON body; conversation_starters own-property guard can reject before transport when config support is false.

useExecutionControls complete body reviewed: discovery requires online, usable, non-Qoder runtime; Qoder selection list is retained otherwise Qoder runtimes are filtered. Successful unsupported discovery becomes empty catalog; loading/error becomes null. changeRuntime clears model/thinking/service tier in one owner update. changeModel delegates to buildModelChangeUpdate.

Model cleanup preserves overrides for null catalog, empty model or unmatched entry; authoritative capability mismatch clears thinking/tier, with zcode advertised thinking default and explicit Standard catalog exception. model-capability normalizes numeric Claude context suffixes on both lookup sides without changing persisted model. Runtime access rejects ownerless runtime, permits unknown viewer, owner, public or explicitly shared private runtime.

EnvTab complete body reviewed: reveal only via button; GET failure leaves unrevealed state. Save handler guards unrevealed and duplicate trimmed keys; bulk parse error is blocked by button disabled state, not an extra handler guard. PUT returns baseline; bulk format failure returns to rows. Optional onSaved is absent at this AdvancedSettings call site; no cache refresh follows here. env-file parser and formatter are local text transforms with no evaluation or transport.

Remaining scope boundaries:

- AdvancedSettings child boundaries: AgentAccessSettings, CustomArgsTab, SkillsTab, McpConfigTab, RuntimeConfigTab, QoderAgentTab, AgentAppsTab and InstructionsTab own further interaction bodies; recorded supporting files/transport candidates do not certify their full descendant trees.
- Inspector picker, avatar, autosave and concurrency child interactions remain separate component boundaries; avatar transport reuses avatar-foreground audit. Activity transcript dialog/detail/timeline child subtree is not certified by reading ActivityTab; reuse issue-query for issue labels and core-query for activity factories.

Validation: all source hashes matched; 90 inventory tuples matched exact ID, method, path_expression and route. Static audit only; root integration review remains.

Root accepted bounded target-source coverage after hash/tuple validation and source spot checks of concrete parent update rollback/cache writes and agent profile hover/presence gates. Supporting child boundaries remain; no full descendant or runtime support claim.
