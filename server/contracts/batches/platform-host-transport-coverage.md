# Platform host transport coverage

Bounded static audit; root review pending. All seven target executable bodies read in full. Supporting modules are separately marked whole_source=false.

`local-directory.ts`: SSR-safe optional desktopAPI discovery; shell detection checks pickDirectory function only. Picker/validator delegate unchanged arguments/results; absent methods return unsupported. No browser filesystem picker or HTTP here.

`local-voice.ts`: SSR-safe voice capability gate requires listModels/onModelsChanged/transcribe only; cast does not validate prepare/download/history members. Interfaces describe native models, PCM and history, not implemented HTTP.

`open-external.ts`: SSR no-op; injected openExternal takes precedence and returned promise is ignored. Otherwise same-tab location.assign or window.open with noopener,noreferrer. Navigation is browser resource behavior; comments do not prove native protocol guards.

`scroll-restoration.tsx`: Context provider and hooks forward optional adapter callbacks. get reads entry; positive top only restoration; ref cleans previous capture before attach/detach, applies positive top/left then registers root. View state writer forwards string/undefined. Active web adapter overrides stale no-provider comments.

`theme-folder.ts`: SSR-safe four-method capability gate; snapshot paths/bytes and write results represent native filesystem content, not URLs or HTTP. No native implementation established.

`use-desktop-unread-badge.ts`: Inbox observer stays enabled while hidden for valid workspace; chat observer enabled only with workspace. Sum uses zero defaults and all session unread_count values. Effect optionally calls setUnreadBadge; absent injection does not prevent query observers.

`use-immersive-mode.ts`: Effect skips entirely when disabled; otherwise optional true call and cleanup false using captured API. No platform test or error handling beyond optional invocation; absent bridge is no-op.

Standard browser/React/Tanstack APIs terminate tracing; no recursive library audit. Static possible request union, not measured execution.

Retained Next WebProviders mounts WebScrollRestorationProvider; the active Vite main.tsx does not mount this provider. Module Maps keyed pathname::key retain offsets/view state per tab until reload. Capture passive scroll listener accepts marked HTMLElements, defaults empty key to main, deletes origin offsets, records height/left; get suppresses writes for 1000ms via performance.now. Cleanup removes listener. Web adapter has no registerScrollRoot/externalSource; hooks optional calls terminate locally.

No desktopAPI implementation found in apps/web; native bridge implementations remain explicit boundaries, not blanket blockers for browser or HTTP closure.

Appearance supporting picker uses input File lists and webkitdirectory; these browser-local files differ from desktop directory path validation. Web duplicate exports ZIP download; native duplicate writes represented files and opens folder. Appearance settings and installed theme state are distinct from filesystem and backendHTTP. Theme CSS source proof is reused without upgrading AST-only claims.

Voice/avatar existing proofs retain browser audio/File/blob/canvas resource versus injected native distinctions. Arbitrary URL navigation is not an invented backend endpoint.

HTTP closure: useDesktopUnreadBadge → useInboxUnreadCount → inboxUnreadSummaryOptions → getInboxUnreadSummary: client:3278 GET /api/inbox/unread-summary; chatSessionsOptions → listChatSessions: client:4106 GET /api/chat/sessions, status=all and workspace header. Both exact current inventory records are copied into JSON. No native badge is required for these observers to exist; no production web mounting of the badge hook was found.

Validation: JSON parsed, current source SHA-256 ledger generated, both IDs and route records resolved against current frontend-calls.json. No app source changed, so npm run check was not run. No runtime, shared inventory, data, Git, network or children changes.
