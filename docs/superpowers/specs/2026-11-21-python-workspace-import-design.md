# Restore TAP in the Python application

The user explicitly requires keeping the Python backend and its SQLite database, migrating the previous local application's data into that database, and retaining the login → capabilities → workspace flow. The default account must reach the original TAP workspace without creating an empty replacement.

Use an explicit, repeatable import from the old SQLite `records` schema into native Python users/workspaces/members plus workspace-scoped content records. Keep the existing development account and session; associate it with TAP as an owner. Preserve the historical Patrick identity and references. Native workspace IDs must be UUIDs, so retain a deterministic ID mapping. Keep each original JSON body for audit. Never rewrite descriptions or other free text during ID translation.

Keep the source database untouched and back up the target using SQLite's backup API before applying schema changes or importing. The import runs in one transaction, rejects conflicts, and skips a completed identical import without overwriting later user edits. A changed source requires an explicit new migration decision rather than silently replacing target records.

The Python application currently lacks the prior content endpoints. Add Python handlers for the operations already supported by the local application, using the imported records and native membership/CSRF checks. Preserve project/task details, comments, skills, squads, conversations, existing stored analytics and contribution history. Unsupported model execution, installation and production integrations continue to fail explicitly. Do not generate new agent output or metrics.

The rejected alternative was restarting the old Node backend; the user specifically corrected this. Directly opening the old database with Python was also rejected because the schemas differ. The selected approach keeps the Python schema and authentication intact while importing the legacy data explicitly.

Acceptance: default email login → capability hub → Enter Workspace opens TAP; imported counts match all 1,225 source records; projects, tasks and their comments are available; analytics uses stored rows; cross-workspace reads/writes are denied; logout and reload work; rerunning import is safe. Keep the original database and backup artifacts available.
