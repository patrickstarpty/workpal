# Schema callback transport coverage

Closed static transport semantics for `packages/core/api/schemas.ts` only. No runtime execution, network access, backend support, or schema correctness claim.

Fresh TypeScript AST verification accounts for all 4,412 call/new expressions: 4,370 Zod API operations, 34 built-in operations, and 8 local-helper calls. All 86 functions/callbacks were extracted and read, including nested callbacks. The companion JSON records exact ranges, source text and SHA-256 hashes, every call category, initializer ranges/hashes, and runtime expression syntax counts. Normal Zod constructor/chaining behavior is the library contract; Zod internals were not inspected.

Custom behavior consists of lenient safeParse/filter pipelines, primitive guards, null/default normalization, status normalization and deduplication, handler membership, recursive schema construction, uniqueness/pagination predicates, fallback object construction, and field projections. The object sanitation callback writes only to a fresh local output object. Billing/subscription callbacks project data; the HTTPS predicate checks a string. Returning URL fields does not navigate.

The only application value import is normalizeIssueStatusCategory. Its directly read source and hash are recorded: comparisons and built-in membership/own-property checks over local literal status constants; its only import is type-only. No further application helper edge remains.

Literal fallbacks, tuples, sets, aliases and spreads create local data. Remaining runtime expressions compose those values and reviewed calls. No request, navigation, filesystem, process, timer, storage, or integration effect was found. Remaining application effects: none.

Validation: fresh AST parse had no diagnostics; counts matched the earlier complete inventory; source SHA-256 matched; all callback ranges/text/hashes and JSON accounting validated. Root independent review remains a workflow step, not an unresolved module effect.
