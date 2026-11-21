# Wrapper candidate classification — incomplete

Root review pending. Fixed 128-candidate set retained exactly once. Preliminary call extraction and concrete matched lines are in the JSON. No whole-source closure is claimed.

The requested precise AST and ambiguous-site classification remains unfinished; do not accept this as a complete classification.

{'text_candidates_requiring_classification': 102, 'client_call_candidates': 26}

## Root AST partition

Parsed all128 current source files with zero diagnostics. Import-bound API call files23; other request/upload/fetch named-interface files26; neither category78; already ledgered1. Counts partition the fixed candidate set. Comments/imports/types alone do not count as calls. Exact method-local tuple references were derived from current ApiClient method spans; this does not establish whole-source semantics or zero I/O.
