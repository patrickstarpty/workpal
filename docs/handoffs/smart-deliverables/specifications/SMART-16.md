# External storage recovery verification protocol
Revision 1. Prepared by Codex. Execution blocked: no external storage environment was used by this audit.

## Environment prerequisites
An authorized isolated storage account/bucket, disposable test objects, documented retention/cleanup rules and a credential delivery channel are required. Do not paste secrets into Activity or reports. Record backend revision, storage adapter version, region/endpoint class and sanitized configuration before execution.

## Test procedure
1. Upload a known small payload and record its digest and durable attachment identifier.
2. Interrupt a larger upload during transfer; record the acknowledgement boundary and resulting server state.
3. Retry using only capabilities that the adapter supports; compare final bytes and count durable objects and associations.
4. Expire authorization, then retry; verify an explicit error with no unauthorized object/metadata access.
5. Cancel while reconnect is pending; verify cancellation wins over late callbacks.
6. Simulate storage success followed by metadata-write failure; verify the documented reconciliation path and absence of accidental deletion of a committed object.
7. Revoke workspace access and attempt read, download and retry.
8. Remove only the disposable objects belonging to this test and record cleanup outcome.

## Required results record
For each step capture start/end time, command or browser action, exact source revision, sanitized response/request trace, expected outcome, actual outcome and pass/fail/not-run. Attach original logs and digest comparison. A skipped step is uncovered scope, never a pass.

## Current actual result
All external-storage cases are NOT RUN. The local filesystem and HTTP test report on SMART-10 is adjacent evidence only; it does not certify this storage adapter. No credentials, external account, measured remote transfer result or release approval is available in this audit.

## Unblocking handoff
The environment owner must supply authorized access through the designated secret mechanism and identify the disposable scope. QA then executes this protocol and produces a new report version. Keep the ticket blocked until those actual results exist.
