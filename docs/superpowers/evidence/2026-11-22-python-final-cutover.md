# Final cutover continuation

In progress; Node retirement not yet performed.

Configuration: root .env generated once with random AUTH_SECRET, mode 0600, Git ignored. npm start/dev/dev:web use native Node env-file loading, environment takes precedence. User authorized replacement secret; sessions require login after restart. No secret recorded here.

Fresh isolated persistence/rollback rehearsal passed against 9bbe7232384a5002fb9b0fe86c5594a7218fd093; artifacts /var/folders/zn/dg1zfbv96p19qstvcpgsjvyr0000gn/T/workpal-persistence-ExAktE. Original source checksum unchanged. Initial imported-workspace browser QA passed. Initial seven-test suite: six pass, one aggregate 30-second timeout; auth-only rerun all five passed. Final suite still required.

Independent review found missing agent image upload chain and missing migration of valuable old browser assertions. Added /api/upload-file and /api/files/{id} using existing fenced upload_intent and LocalBlobStore, authenticated workspace authorization, bounded multipart and image signature check. Test first failed on missing route, then passed restart/access/oversize/CSRF/unsupported-association checks. Python test upload path is isolated. Initial development of test used default uploads directory and left unreferenced test image bytes there; no real SQLite records changed. Preserve those files pending explicit reconciliation rather than deleting unrelated uploads.

Migrating avatar-channels, web-components, mock-data and contribution assertions into Python import QA, retaining product assertions rather than deleting them. Brand storage migration test remains valuable and must be retained.

## Scope correction after user clarification

User reasserted one-to-one in-scope Go compatibility, not merely mock retirement. Original python-go-backend spec already requires route-by-route Go contract acceptance. routes.json exists but remains mostly pending; current local workspace_content adapters and passing product tests are not equivalent to Go contract completion. Do not delete Node or claim migration complete on cutover smoke evidence. No real service has been stopped and no real DB backup/freeze or Node deletion has occurred in this continuation.

Expanded Python product QA passed all four migrated modules, including avatar upload, 14 routes, command/chat shortcuts, squad scope navigation, analytics filtering and contribution import. Pre-retirement npm run check passed. These are scoped product results only, not Go parity. Further work must reconcile batch evidence with routes.json and migrate missing in-scope Go behavior before retirement.
