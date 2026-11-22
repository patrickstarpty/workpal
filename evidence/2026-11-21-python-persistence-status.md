# Python persistence evidence

- `npm run build`: exit 0.
- `node scripts/python-persistence-qa.mjs`: exit 0 (final run, 2026-11-21).
- Script starts `npm start` on isolated port 24374, with temporary Python SQLite, random auth secret and Redis prefix, Redis `redis://127.0.0.1:26379`. No Redis flush. Legacy source opened read-only and backed up before import; real SQLite never written.
- Browser: sign in → workspace → manual issue creation → detail description edit → ordinary comment submission → refresh. Created issue `dd266c88-07ac-476b-abce-664070aafa0e`; title, changed description and comment visible before and after stopping the owned service and restarting with the same SQLite.
- Product HTTP DELETE removes imported task `TAP-029` in the isolated copy. Both before and after restart: HTTP GET 404 and browser “Issue not found”.
- Console: `PASS before restart dd266c88-07ac-476b-abce-664070aafa0e TAP-029`; `PASS after same-database restart dd266c88-07ac-476b-abce-664070aafa0e TAP-029`.
- Artifacts: `/var/folders/zn/dg1zfbv96p19qstvcpgsjvyr0000gn/T/workpal-persistence-FLewYF` (SQLite and service log retained).
- Fixes reproduced through the script: missing ordinary comment POST persistence; issue lookup failed after frontend canonicalized UUID route to issue identifier. Added scoped ordinary comment storage and workspace-scoped identifier GET lookup. Unsupported execution/attachment/reply variants still fail explicitly.
- Cleanup signals only the script-owned npm process group; launcher stops its owned Python children. External port 4174 service preserved.
- Not covered: full project CRUD, comment editing/deletion, agent execution, integrations, WS, complete Task 4 acceptance, real frozen rollback/deletion. No full check, commit, push or PR performed. Node and unrelated archived outputs preserved.
