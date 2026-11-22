# Schema/data transport coverage

Static, partial audit for root review. No runtime execution, network, git, shared inventory, or child work was performed. Full AST coverage is distinct from semantic closure.

- `packages/core/types/agent.ts`: **closed-local-static**; SHA-256 `a1c494eb9f71de1f08350415eb1b41777387e601da6ace53ba4d639d193c640b`. 2 runtime declarations, 0 calls/new expressions, 0 functions/callbacks.
- `packages/core/api/schemas.ts`: **remaining-semantic-review**; SHA-256 `f75704eeb37705c0f72b4bd89ff89e848289f3fe7cee154b9bed7ff280be674d`. 437 runtime declarations, 4412 calls/new expressions, 86 functions/callbacks.
- `packages/views/dashboard/utils.ts`: **remaining-semantic-review**; SHA-256 `0291f572d74f9a3c8bfd995563b4be97d8ff2a3ba63dcdaef3ccf70fadfcbf22`. 31 runtime declarations, 161 calls/new expressions, 59 functions/callbacks.

Agent runtime closure: lines 114–145 define the protocol-family string tuple; lines 150–153 spread that local tuple and append `omp`. Other top-level declarations erase as types; both imports are type-only. No runtime calls remain.

Schemas and dashboard remain open. JSON retains every complete runtime declaration, function/callback, call anchor, import distinction and explicit remaining declaration range. These retained sources were mechanically extracted, not claimed as fully read. Only schemas lines 550–561 and 3575–3578 and dashboard lines 1–90 were inspected in bounded reads. Earlier grep output was truncated and is not semantic evidence.

Confirmed schema behavior: lenientArray independently safe-parses items and drops failed items; StripeHostedURLSchema requires HTTPS after library URL validation, without restricting host or performing navigation. Caller navigation and request/refetch behavior remain outside the closed evidence. Imported status, failure-classification, date and cost helper dependencies remain explicitly listed in JSON. Normal Zod constructors and built-ins terminate at their API contracts.

Validation: all three complete files parsed with TypeScript without parse diagnostics; recorded hashes matched source bytes. JSON parsed successfully. Application checks were intentionally not run for this static-only artifact task. Root must complete bounded semantic reads and helper tracing before closing the two remaining files; no global completion or runtime support is asserted.

## Parent review

`agent.ts` structural closure accepted. Dashboard utils now closed for bounded transport audit after complete emitted-runtime review and explicit date/cost/failure helper tracing. Pricing uses local numeric tables, candidate string normalization and Zustand state persisted through localStorage; no HTTP requests. Dependency hashes are recorded. Schema module remains partial. No numerical pricing correctness or backend support claim.
