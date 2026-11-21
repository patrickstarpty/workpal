# Issue detail transport audit — incomplete

Target: `packages/views/issues/components/issue-detail.tsx` (4,580 lines). This is an open handoff, not a completed coverage proof. Root review is required. No backend or global coverage claim is made.

The aggregate read was truncated and cannot establish full own-body coverage. `whole_source` is therefore false. The JSON records confirmed query gates and callback wiring, separate candidate-proof snapshots, and explicit remaining work. Empty edges and frontend-call inventories mean unestablished coverage, not absence of transport.

Current source hashes matched all file entries in the mutation (38), query (4), cache (7), ws updater (1), comment card (1), inline run (10), composer (15), and issue menu (1) candidate proofs. Their content and executed-symbol applicability remain to be reviewed. The editor candidate exposes no `files` entries, so its source validation has not been established.

Remaining work: complete independent <=100-line untruncated reads; resolve bounded helpers and save/error/settlement branches; map executed hooks to scoped proofs; obtain exact invoked-client tuples; enumerate the finite refetch union and persistence/resource lifetimes. Do not close this target from this artifact.

Explicit exclusions: rendered arbitrary descendant trees, native host adapters, and third-party internals. Only static filesystem inspection and the three authorized new artifact writes were performed; no runtime/tests/network/model/data/git/shared inventory/ledger changes or children.

## Root composed source acceptance

Combined five contiguous source ranges1–4580 using helper/query/edit/render proofs. Exact requests, callback branches, local helper effects and query gates reconciled. Source/proof hashes and finite request union are in JSON. Earlier truncated-read checkpoints are superseded. Acceptance concerns application source transport coverage only, not backend capability or parity.
