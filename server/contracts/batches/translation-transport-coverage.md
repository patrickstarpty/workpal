# Translation transport coverage

Bounded audit: en.ts, ja.ts, ko.ts and zh.ts in apps/web/features/landing/i18n. The companion JSON records current SHA-256 hashes, parse results, full AST node/expression histograms and anchored structural edges for all four files and their local value dependencies. Type-only imports have no runtime evaluation.

All four complete factory bodies construct dictionary data. English and Chinese spread their site copy; Japanese and Korean first call createEnDict, spread its local result, then spread their locale site copy. The eight site/demo modules contain data initializers and type-only dependencies beyond the site-to-demo value imports. No factory callback, request, dynamic import or constructor is present. Literal URL content does not execute requests. Shared githubUrl and discordUrl are empty strings.

The shared module also imports cn. Its complete executable bodies comprise three JSX icon functions and heroButtonClassName, which calls cn with local class strings. None is called by these dictionaries. packages/ui/lib/utils.ts initializes twMerge through extendTailwindMerge and defines cn as twMerge(clsx(inputs)). Its complete local body is covered.

**Remaining edge for each dictionary:** module evaluation of shared.tsx reaches utils.ts and external tailwind-merge's extendTailwindMerge initialization. This audit does not close that external implementation/dependency chain. Consequently the four dictionary bodies are structurally covered, but none is promoted to fully closed runtime-source disposition. No exact HTTP transport is evidenced in the bounded local bodies.

Validation: all 14 recorded sources parse successfully with the installed TypeScript compiler; hashes and every source anchor were checked against disk. No application execution, network/model calls, shared-ledger edits or git mutations. This is not global/backend completion.

## Parent dependency review

The earlier remaining edge is resolved for this transport audit: installed tailwind-merge 3.5.0 `extendTailwindMerge` (bundle line 3285) calls `createTailwindMerge` (464–487), which returns a lazy closure. Dictionary construction never invokes that closure or `cn`. All four dictionary dispositions are accepted. This bounded proof does not claim a third-party supply-chain audit. Installed bundle hash and anchors are recorded in JSON.
