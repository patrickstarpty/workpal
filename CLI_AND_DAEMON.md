# CLI and Agent Daemon Guide

The `workpal` CLI connects your local machine to Workpal. It handles authentication, workspace management, issue tracking, and runs the agent daemon that executes AI tasks locally.

## Installation

### Homebrew (macOS/Linux)

```bash
brew install workpal-ai/tap/workpal
```

### Build from Source

```bash
git clone https://code-host.invalid/workpal.git
cd workpal
make build
cp server/bin/workpal /usr/local/bin/workpal
```

### Update

```bash
brew upgrade workpal-ai/tap/workpal
```

For install script or manual installs, use:

```bash
workpal update
```

`workpal update` uses GitHub Releases by default. Self-hosted installations can
point the CLI at a GitHub Releases-compatible metadata mirror and an artifact
mirror without changing the command. To let a daemon poll that source, also
enable self-update explicitly because self-hosted auto-update is disabled by
default:

```bash
export WORKPAL_RELEASE_API_BASE_URL=https://updates.example/api
export WORKPAL_RELEASE_DOWNLOAD_BASE_URL=https://updates.example/releases/download
export WORKPAL_DAEMON_AUTO_UPDATE=true
workpal update
```

The metadata mirror must serve `/repos/workpal-ai/workpal/releases/latest` and
`/repos/workpal-ai/workpal/releases/tags/<tag>`. The artifact mirror must serve
`/<tag>/<asset-name>` and preserve the published `checksums.txt` contents.
When these variables are unset, the GitHub defaults remain unchanged.

## Quick Start

```bash
# One-command setup: configure, authenticate, and start the daemon
workpal setup

# For self-hosted (local) deployments:
workpal setup self-host
```

Or step by step:

```bash
# 1. Authenticate (opens browser for login)
workpal login

# 2. Start the agent daemon
workpal daemon start

# 3. Done — agents in your watched workspaces can now execute tasks on your machine
```

`workpal login` automatically discovers all workspaces you belong to and adds them to the daemon watch list.

## Authentication

### Browser Login

```bash
workpal login
```

Opens your browser for OAuth authentication, creates a 90-day personal access token, and auto-configures your workspaces.

### Token Login

```bash
workpal login --token <mul_...>
```

Authenticate using a personal access token directly. Useful for headless environments. Pass `--token=` with an empty value to be prompted interactively (so the token never lands in shell history).

### Check Status

```bash
workpal auth status
```

Shows your current server, user, and token validity.

### Logout

```bash
workpal auth logout
```

Removes the stored authentication token.

## Agent Daemon

The daemon is the local agent runtime. It detects available AI CLIs on your machine, registers them with the Workpal server, and executes tasks when agents are assigned work.

### Start

```bash
workpal daemon start
```

By default, the daemon runs in the background and writes its log into the state
directory of the profile it was started with — **not always `~/.workpal/`**:

| Profile | State directory |
| --- | --- |
| Default (no `--profile`) | `~/.workpal/` |
| Named (`--profile <name>`) | `~/.workpal/profiles/<name>/` |

That directory holds `daemon.log` (the log), `daemon.pid` (the background
daemon's PID), and `daemon.err.log` (raw crash output; near-empty on a healthy
daemon, since normal logging goes to `daemon.log`).

The Desktop app runs its own named profile, so on a machine that has ever run
both, `~/.workpal/daemon.log` and `~/.workpal/profiles/<name>/daemon.log` both
exist and both read as plausible logs — only one is being written to. Don't
guess: `workpal daemon logs` prints the absolute path it resolved (see
[Logs](#logs)).

To run in the foreground (useful for debugging):

```bash
workpal daemon start --foreground
```

#### Following a replaced binary

A CLI-launched daemon periodically compares its own compile-time version against
the `--version` output of the `workpal` binary it would re-exec. When they differ
— `brew upgrade workpal`, a re-download, a local `make build` — it waits for any
running task to finish, then restarts into the new binary. A running task is
never interrupted; if the daemon is busy the restart is deferred to the next
check, and `workpal daemon status` shows why it's still on the old version.

This is separate from the GitHub self-update poller: disabling that does not stop
the daemon from following a binary you installed yourself. To turn it off:

```bash
WORKPAL_DAEMON_AUTO_RELOAD=0 workpal daemon start
# or
workpal daemon start --no-auto-reload
# or persist it
workpal config set disable_auto_reload true
```

Agent CLIs (codex, claude, ...) are handled differently: when one of them is
upgraded in place, the daemon re-probes its version and re-registers the runtime
**without restarting**, so subsequent tasks pick up the new CLI while Workpal's
availability stays independent of a third party's release cadence.

Desktop-managed daemons ignore both, because the Desktop app owns its bundled
CLI's lifecycle.

### Boot autostart

Opt-in: only `workpal daemon autostart enable` registers the profile's
daemon with the OS, so the machine brings it back after a reboot or re-login
— without that, every reboot takes the runtime offline and queued runs sit
unclaimed. `daemon start` never registers on its own: it prints a one-line
hint when nothing is registered, and otherwise stays out of the way.

| Platform | Mechanism | Where |
| --- | --- | --- |
| Windows | Per-user Run key | `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, value `Workpal` |
| macOS | launchd LaunchAgent | `~/Library/LaunchAgents/ai.workpal.daemon.plist` (runs at login) |
| Linux | systemd user unit | `~/.config/systemd/user/workpal-daemon.service`; without systemd, an XDG autostart entry under `~/.config/autostart/` |

Each entry runs `workpal daemon start --foreground` for that profile — named
profiles get their own entry, so several daemons on one machine never collide.
Daemon settings are read from the profile's config (`workpal config set ...`)
at start. Shell environment variables do **not** travel into a login session:
only `PATH` is snapshotted at registration (and refreshed while Workpal owns
the entry), which is what keeps agent CLIs installed via Homebrew, nvm, or a
user bin directory discoverable — persist everything else with
`workpal config set` or your user environment. On Linux, `enable` also tells
you (it does not run it for you) how to `loginctl enable-linger $USER` so a
headless machine starts the unit at boot rather than at first login.

```bash
workpal daemon autostart enable         # the only thing that registers
workpal daemon autostart status         # what is registered, and where
workpal daemon autostart status --output json
workpal daemon autostart disable        # remove the registration
```

Refresh: while an entry exists and carries Workpal's ownership marker,
`daemon start` silently rewrites it so a moved executable (a Homebrew
upgrade, a self-update) heals. An entry at the same path that Workpal did
not create — your own systemd unit, a hand-written LaunchAgent — is never
refreshed and never overwritten: `enable`/`disable` refuse it and say which
file is in the way, and the refresh is additionally skipped when the daemon
was launched by an external supervisor (systemd `INVOCATION_ID` for a unit
that is not ours).

`daemon stop` stops the daemon but keeps the registration — it says nothing
about the next boot; `autostart disable` is what turns that off. Disabling
never disturbs a running daemon: on Linux the wants link is removed while
the managed unit file stays (unlinked), so the current session keeps the
unit's restart policy across a binary update and only the next-login start
goes away; on macOS the plist is deleted without a `launchctl bootout`, so
the process launchd is supervising keeps running. Daemons started by the
Workpal Desktop app are never registered or refreshed here: the app owns
that daemon's lifecycle through its own app-start daemon preference.

### Stop

```bash
workpal daemon stop
```

### Status

```bash
workpal daemon status
workpal daemon status --output json
```

Shows PID, uptime, detected agents, and watched workspaces.

### Logs

```bash
workpal daemon logs              # Last 50 lines
workpal daemon logs -f           # Follow (tail -f)
workpal daemon logs -n 100       # Last 100 lines
workpal daemon logs --profile staging
```

Every run first prints the absolute path it resolved, so you always know which
profile's log you are looking at:

```
$ workpal daemon logs -n 100
Reading /Users/you/.workpal/profiles/desktop-mbp/daemon.log (profile: desktop-mbp)
...
```

That line goes to stderr, before the tail starts — so it also shows up under
`-f`, and piping or redirecting the command still yields log content only:

```bash
workpal daemon logs -n 500 | grep ERROR   # the path line is not in the pipe
```

Without `--profile`, the default profile's log is read. If it doesn't exist the
command says so and names the path it looked for, which is the fastest way to
find out that the daemon you care about is running on a different profile —
`workpal daemon status --profile <name>` confirms which one is live.

### Supported Agents

The daemon auto-detects these AI CLIs on your PATH:

| CLI | Command | Description |
|-----|---------|-------------|
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | `claude` | Anthropic's coding agent |
| [Antigravity CLI](https://antigravity.google/docs/cli-install) | `agy` | Google Antigravity CLI |
| [CodeBuddy Code](https://www.codebuddy.ai/docs/cli/quickstart) | `codebuddy` | Tencent CodeBuddy Code (reads `CODEBUDDY.md`, not `CLAUDE.md`) |
| [Huawei Cloud CodeArts](https://support.huaweicloud.com/usermanual-cli/codeartsagent_cli_0001.html) | `codearts` | Huawei Cloud coding agent (OpenCode-compatible JSON protocol) |
| [DevEco Code](https://gitcode.com/openharmony-sig/deveco-code) | `deveco` | OpenHarmony DevEco Code |
| [Codex](https://github.com/openai/codex) | `codex` | OpenAI's coding agent |
| [GitHub Copilot CLI](https://docs.github.com/en/copilot) | `copilot` | GitHub's coding agent (model routed by your GitHub entitlement) |
| OpenCode | `opencode` | Open-source coding agent |
| Muse Code | `muse` | Muse Session Protocol via `muse serve` |
| ZeroClaw | `zeroclaw` | ACP via `zeroclaw acp`; model is managed by ZeroClaw |
| [ZCode](https://zcode.z.ai/) | `zcode` / ZCode Desktop | Native NDJSON app-server, sessions, model discovery, thinking levels, MCP and yolo execution |
| OpenClaw | `openclaw` | Open-source coding agent |
| Hermes | `hermes` | Nous Research coding agent |
| [Pi](https://pi.dev/) | `pi` | Pi coding agent |
| Oh-My-Pi | `omp` | Oh-My-Pi coding agent (Pi fork) |
| [Cursor Agent](https://cursor.com/) | `cursor-agent` | Cursor's headless coding agent |
| Kimi | `kimi` | Moonshot coding agent |
| [Reasonix](https://github.com/esengine/DeepSeek-Reasonix) | `reasonix` | DeepSeek-focused ACP coding agent (run `reasonix setup` first) |
| Dim | `dim` | DimCode ACP coding agent (speaks the ACP protocol via `dim acp`) |
| [Devin CLI](https://docs.devin.ai/cli/quickstart) | `devin` | Version 3000.3.22+. Host-local ACP (`devin acp`), not cloud Devin VMs. Run `devin auth login` first. |
| Kiro CLI | `kiro-cli` | Kiro ACP coding agent |
| [Qoder CLI](https://docs.qoder.com/) | `qodercli` | Qoder ACP coding agent |
| [Qoder CN CLI](https://help.aliyun.com/en/lingma/qodercli-cn/product-overview/what-is-qoder-cli-cn) | `qoderclicn` | Qoder CN ACP coding agent |
| [Trae](https://docs.trae.cn/cli) | `traecli` | ByteDance TRAE CLI (ACP via `traecli acp serve`) |
| [Grok Build CLI](https://docs.x.ai/) | `grok` | xAI Grok Build CLI (ACP via `grok agent stdio`) |
| [Qwen Code](https://github.com/QwenLM/qwen-code) | `qwen` | Alibaba Qwen Code (`qwen -p` with stream-json) |
| [Amp](https://ampcode.com/docs/cli) | `amp` | Local `amp --execute --stream-json`; requires an access token in `AMP_API_KEY` for unattended execution. Model configuration selects an Amp mode. Managed MCP and live supplements are unsupported. |
| [Factory Droid](https://docs.factory.com/droid-exec/overview) | `droid` | Native CLI 1.8.0+, `droid exec` with stream-json; sign in or set `FACTORY_API_KEY`. Uses `--auto high`; Workpal-managed MCP and live supplements are unsupported. |
| [QwenPaw](https://github.com/agentscope-ai/QwenPaw) | `qwenpaw` | QwenPaw ACP coding agent (ACP via `qwenpaw acp`; model is fixed by its own configuration) |
| [MiniMax Code](https://github.com/MiniMax-AI/minimax-code) | `mcode` | MiniMax Code ACP coding agent (ACP via `mcode acp`; model is managed by MCode) |
| [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) | `dsh` | DeepSeek Harness (`dsh --profile workpal --stdio`; requires the Workpal runtime profile to be installed; reads AGENTS.md and .dsh/skills/) |

You need at least one installed. The daemon registers each detected CLI as an available runtime.

Pi and Oh-My-Pi require kernel support for process identity signalling to clean
up detached tools safely: on Linux, `pidfd_open` and `pidfd_send_signal` (kernel
5.3 or newer); on macOS, kernel-checked process identity signalling. Each run
checks these operations before launching the runtime. An unsupported or denied
probe operation, including one blocked by a sandbox, fails startup with a
compatibility error instead of allowing work to start without the required cleanup
capability. This is a capability check, not a kernel version check, and a passing
probe does not guarantee permission to signal every descendant process. Existing runs blocked by
unconfirmed cleanup still require inspection and a manual rerun; the startup check
does not clear those blocks or establish that earlier background processes exited.

### How It Works

1. On start, the daemon detects installed agent CLIs and registers a runtime for each agent in each watched workspace
2. The server pushes a wake signal over the WebSocket connection when work is waiting, and the daemon claims across all of its runtimes in one batch. A periodic poll (default: 30s) runs as the catch-up path — a wake signal cuts the wait short, so this interval puts no floor under normal task pickup; it bounds how long work can sit when a signal is missed or the connection is down
3. When a task arrives, it creates an isolated workspace directory, spawns the agent CLI, and streams results back
4. Heartbeats are sent periodically (default: 15s) so the server knows the daemon is alive
5. On shutdown, all runtimes are deregistered

### Local Environments

The issue sidebar's **Environments** section lists the servers and desktop apps associated with an issue's runs, grouped by the machine they run on. A localhost URL opens only on that machine. The daemon reports environments in two ways:

- **Detected.** On macOS and Linux, any process listening on a TCP port whose working directory is inside a run's directory shows up. It has to be seen on two scans in a row, about 30 seconds apart, so short-lived test servers stay out. The agent CLIs themselves are ignored, and so are servers in a project's own local directory, which the user started.
- **Declared.** A repository can describe its environments in `.workpal/environments.toml`. An agent starts one with `workpal env start <name>`. The daemon then supervises it: the environment keeps running after the run ends and stops at its TTL. If it is still running when the daemon restarts, the new daemon process picks it back up.

```toml
[environments.web]
label = "Web app"
start = "pnpm dev --port $WORKPAL_PORT"
# url defaults to http://localhost:$WORKPAL_PORT; set url = "" when there is none
# ready = "http://localhost:$WORKPAL_PORT/health"   # defaults to url
# stop = "docker compose down"                      # runs before the process group is signalled
ttl = "24h"                                         # 1m to 7d, default 24h
```

Each environment gets ten ports, `WORKPAL_PORT` through `WORKPAL_PORT+9`. Parallel runs therefore never collide. `start` runs with `/bin/sh -c` from the directory that holds `.workpal/`, with the caller's `PATH`. The daemon's `WORKPAL_*` credentials are not passed to it. Output goes to a log under `<workspaces root>/.environments/v1/`, and `workpal env start` prints its path. The full log file stays on the machine; the daemon can send portions of it to the server for the sidebar, as described below.

```bash
workpal env start web          # waits until the ready URL answers below 500, then prints the URL
workpal env start web --wait=false
workpal env list
workpal env stop web
```

A declared environment's own servers are not listed a second time as detected ones. That includes servers its `start` command detaches into process groups of their own, as long as they stay in the session `start` runs in. When two environments from the same checkout share a server, such as one API, and the one that started it ends, the server passes to the other while it runs. When such an environment has no URL and one of its processes is a desktop app, the sidebar shows the environment as that app, and Desktop on the same machine can bring its window forward.

These commands use the running task's credential, so they work only inside a run. Environments belong to the issue, which means a later run on the same issue can list and stop what an earlier one started. Neither detected nor declared environments are supported on Windows yet.

#### Sidebar controls

- **Declared environments:** use **+** to start an environment reported by the latest run on a machine, using that run's checkout. An environment's menu offers **Stop**, **Restart**, and **View logs**. Restart reads the repository's current declaration, so it needs the checkout and `.workpal/environments.toml` to still exist.
- **Detected servers:** the menu offers **Stop**, with confirmation. They have no captured log or restart command.
- **Detected desktop apps:** Desktop on the same machine can bring their window forward. They cannot be stopped or restarted from the sidebar; declare the app as an environment to manage its lifecycle there.

Starting, stopping, or restarting requires a human workspace member who can access the issue and use the machine. The machine must be online and its daemon must support environment controls; an older daemon requires an update. Reading logs requires access to the issue, but not permission to control the machine. Sidebar actions work without an active agent run; the CLI commands above still require a run's credential.

#### Logs shared with the issue

**View logs** reads the last 500 lines, capped at 256 KiB per request, from a declared environment. While the environment is live, the dialog follows its output by requesting another tail about every five seconds. You can pause following, refresh, search, wrap, or copy the displayed output. Read the local file on the machine when you need the complete log.

A crashed declared environment also reports a short excerpt automatically: its last two non-empty log lines, each truncated to 240 characters. The sidebar can show that excerpt even when the machine is offline; a fresh log read needs the machine online.

The server applies secret redaction to uploaded log tails and crash excerpts before storing them. Log-read records are eligible for deletion after ten minutes and are removed by a sweeper that runs every minute. Crash excerpts are stored separately with the environment record, so that ten-minute cleanup does not remove them. Anyone with access to the issue can read the shared output; do not rely on redaction to make arbitrary application logs safe to share.

### Configuration

Daemon behavior is configured via flags or environment variables:

| Setting | Flag | Env Variable | Default |
|---------|------|--------------|---------|
| Poll interval | `--poll-interval` | `WORKPAL_DAEMON_POLL_INTERVAL` | `30s` (catch-up fallback; WebSocket wake signals deliver work sooner) |
| Healthy WebSocket claim poll upper bound | `--ws-claim-poll-interval` | `WORKPAL_DAEMON_WS_CLAIM_POLL_INTERVAL` | `3m` (configured independently of `--poll-interval`; downward jitter makes the normal interval `2m30s`–`2m45s`, while old servers and uncertain claims retain the ordinary poll interval) |
| Heartbeat interval | `--heartbeat-interval` | `WORKPAL_DAEMON_HEARTBEAT_INTERVAL` | `15s` |
| Agent timeout | `--agent-timeout` | `WORKPAL_AGENT_TIMEOUT` | `0` (no cap; bounded by the watchdogs) |
| Agent idle watchdog | — | `WORKPAL_AGENT_IDLE_WATCHDOG` | `2h` (`0` disables the whole watchdog suite) |
| Agent tool watchdog | — | `WORKPAL_AGENT_TOOL_WATCHDOG` | same as the idle watchdog (`0` = never force-stop during a tool call) |
| Codex semantic inactivity timeout | `--codex-semantic-inactivity-timeout` | `WORKPAL_CODEX_SEMANTIC_INACTIVITY_TIMEOUT` | same as the idle watchdog (Codex's timer is not tool-aware, so it tracks the larger of the idle / tool budgets) |
| Codex first-turn no-progress timeout | — | `WORKPAL_CODEX_FIRST_TURN_TIMEOUT` | `0` (keeps the built-in `60s` ceiling) |
| Codex handshake timeout | `--codex-handshake-timeout` | `WORKPAL_CODEX_HANDSHAKE_TIMEOUT` | `30s`; `thread/start` and `thread/resume`: `60s` (an explicit value overrides both budgets globally) |
| Codex turn-interrupt timeout | — | `WORKPAL_CODEX_TURN_INTERRUPT_TIMEOUT` | `2s` (bounded grace period for `turn/interrupt` acknowledgement and `turn/completed`; tune from the logged interrupt latency on unusually slow hosts) |
| OpenCode idle watchdog | — | `WORKPAL_OPENCODE_IDLE_WATCHDOG` | `10m` (`0` falls back to the generic idle watchdog; cannot extend it) |
| Max concurrent tasks | `--max-concurrent-tasks` | `WORKPAL_DAEMON_MAX_CONCURRENT_TASKS` | `20` |
| Daemon ID | `--daemon-id` | `WORKPAL_DAEMON_ID` | hostname |
| Device name | `--device-name` | `WORKPAL_DAEMON_DEVICE_NAME` | hostname |
| Runtime name | `--runtime-name` | `WORKPAL_AGENT_RUNTIME_NAME` | `Local Agent` |
| Workspaces root | — | `WORKPAL_WORKSPACES_ROOT` | `~/workpal_workspaces` |
| GC enabled | — | `WORKPAL_GC_ENABLED` | `true` (set `false`/`0` to disable) |
| GC scan interval | — | `WORKPAL_GC_INTERVAL` | `2h` |
| GC TTL (done/cancelled issues) | — | `WORKPAL_GC_TTL` | `24h` |
| GC completed-task TTL (issue tasks) | — | `WORKPAL_GC_COMPLETED_TASK_TTL` | `14d` (set `0` to disable) |
| GC orphan TTL (no `.gc_meta.json`) | — | `WORKPAL_GC_ORPHAN_TTL` | `72h` |
| GC artifact TTL (completed tasks) | — | `WORKPAL_GC_ARTIFACT_TTL` | `12h` (set `0` to disable) |
| GC artifact patterns | — | `WORKPAL_GC_ARTIFACT_PATTERNS` | `node_modules,.next,.turbo` |
| GC repo cache TTL (`.repos`) | — | `WORKPAL_GC_REPO_TTL` | `720h` (30d; set `0` to disable) |
| GC repo maintenance | — | `WORKPAL_GC_REPO_MAINTENANCE_ENABLED` | `true` (set `false`/`0` to disable heavy Git maintenance only) |
| GC Hermes memory TTL (per-agent `memories/`) | — | `WORKPAL_GC_HERMES_MEMORY_TTL` | `2160h` (90d; set `0` to disable) |
| GC Hermes session TTL (per-conversation `state.db`) | — | `WORKPAL_GC_HERMES_SESSION_TTL` | `336h` (14d; set `0` to disable) |
| GC task temp legacy TTL (pre-lock `workpal-task-*`) | — | `WORKPAL_GC_TASK_TEMP_LEGACY_TTL` | `0` (disabled; set a duration to opt in) |

#### Workspace garbage collection

The daemon periodically scans `WORKPAL_WORKSPACES_ROOT` for cleanup. The active-directory guard uses the resolved path so a symlink or Windows junction and its target share the same guard.

- **Full task cleanup** — when an issue's status is `done` or `cancelled` and has been idle for `WORKPAL_GC_TTL`, the entire task directory is removed.
- **Completed-task retention bound** — `WORKPAL_GC_COMPLETED_TASK_TTL` fully removes an inactive issue task once its `.gc_meta.json` `completed_at` age exceeds the configured duration, even while the parent issue remains open. Cleanup waits for a successful parent-issue status check, never removes an active environment, and never fully removes a `local_directory` environment. A later rerun provisions a fresh environment instead of resuming the removed checkout.
  - The default is `14d` on every server, Workpal Cloud and self-host alike. Set the variable to change it; an explicit `0` disables the policy and keeps every completed environment until its issue becomes `done` or `cancelled`.
  - Removing an environment discards work an agent left uncommitted or unpushed on its branch, along with that task's `output/` and `logs/`. The per-issue Codex session store lives outside `WORKPAL_WORKSPACES_ROOT` under its own TTL, so a later rerun still resumes the agent's prior session — it just starts from a fresh checkout. Size the TTL against that trade, and keep it comfortably above `WORKPAL_GC_INTERVAL`: the active-root guard protects a task that is currently running, not one whose follow-up run is queued but unclaimed.
- **Orphan cleanup** — task directories with no `.gc_meta.json` (e.g. left over from a daemon crash) are removed once they exceed `WORKPAL_GC_ORPHAN_TTL`.
- **Artifact-only cleanup** — when a task has been completed for at least `WORKPAL_GC_ARTIFACT_TTL` but the issue is still open, regenerable build outputs whose directory basename matches `WORKPAL_GC_ARTIFACT_PATTERNS` are removed. The daemon also reclaims the exact managed path `codex-home/.sandbox-bin`; old task metadata without `completed_at` becomes eligible for this managed-only cleanup after its `.gc_meta.json` file has been idle for `WORKPAL_GC_ORPHAN_TTL`. The rest of the task (source, `.git`, `output/`, `logs/`, `.gc_meta.json`, Codex auth/config/session state) is preserved so the agent can resume it. The same basename patterns apply to unarchived chats that use a daemon-managed work directory once the chat status check succeeds and the last run has been complete for `WORKPAL_GC_ARTIFACT_TTL`. After a successful cleanup, the daemon skips repeat scans for that run. A later completed run becomes eligible again after the same delay.
- **Managed-cache reclamation** — the exact managed path above is reclaimed for *every* task kind once the task has been completed for `WORKPAL_GC_ARTIFACT_TTL`, not just for issue tasks whose issue is still open. It applies even while the parent record says the directory itself must stay — an active chat session, a still-running autopilot run — and even when the parent record could not be reached this cycle, because the contents are regenerable and the next run re-provisions them on demand. A task currently running on the directory is never touched. Set `WORKPAL_GC_ARTIFACT_TTL=0` to disable this along with the rest of artifact cleanup.

- **Repo cache eviction** — the bare git clones under `.repos/` are shared object stores: each task workdir is a `git worktree` off one of them rather than its own clone, so a task's `.git` is only a pointer file. They are evicted only when all of the following hold: the repo is no longer attached to any workspace this daemon watches, it has no worktrees left, and no task has created a worktree from it for `WORKPAL_GC_REPO_TTL`. A cache created before this stamp existed is not treated as ancient — its clock starts at the first GC cycle that sees it, so upgrading does not wipe every cache. Evicting is safe by construction: the next task that needs the repo re-clones it on demand, so a wrong eviction costs a clone, not a failure.

  Short worktree cleanup and eligible cache eviction continue on every GC cycle, including while agents are active. Heavy repo maintenance (`reflog expire` and `git gc`) starts only while the daemon is otherwise idle. A checkout or newly claimed task cancels it and takes priority; interrupted work remains pending for a later idle GC cycle. Operators can disable only these heavy commands with `WORKPAL_GC_REPO_MAINTENANCE_ENABLED=false` without disabling worktree cleanup or cache eviction.

- **Hermes session store reclamation** — a conversation's Hermes transcript (`state.db`) lives at `<profile dir>/hermes-sessions/<agent-id>/<hermes-profile>/<conversation>/`, outside any task directory, so a follow-up turn can resume it (see [Hermes agent memory](#hermes-agent-memory)). A store untouched for `WORKPAL_GC_HERMES_SESSION_TTL` is removed. The default matches the Codex session store rather than the memory store above: these hold full transcripts, and reclaiming an idle one costs a thread that starts fresh (with a continuity notice), not an agent that forgot what it learned. A store a running task holds is never reclaimed.
- **Hermes memory store reclamation** — a Hermes agent's long-term memory (`memories/`) lives at `<profile dir>/hermes-state/<agent-id>/<hermes-profile>/`, outside any task directory, so it survives across tasks and issues (see [Hermes agent memory](#hermes-agent-memory)). A store untouched for `WORKPAL_GC_HERMES_MEMORY_TTL` is removed, giving a deleted agent's memory an eventual-reclamation guarantee. The default is deliberately long: these are a handful of markdown files, and reclaiming one is user-visible amnesia rather than a cache miss. A store a running task holds is never reclaimed.
- **Task temp dir reclamation** — every task gets a private temp directory (`workpal-task-*`) under the system temp base (`/tmp`, or `WORKPAL_AGENT_TEMP_BASE`), exported to the agent as `TMPDIR`/`TMP`/`TEMP`. On Windows, every task instead inherits the daemon user's `TMP`/`TEMP`: Git Bash's `/tmp` mount is shared by all of the user's live Git Bash processes, whichever runtime started them, so it must never point at a task directory that will be deleted. `TMPDIR` stays task-local, and for Claude Code `CLAUDE_CODE_TMPDIR` defaults to that directory unless the user overrides it. It is removed when the run ends, but that removal never happens when the daemon is killed and does not succeed while a file inside is still open — common on Windows, where an open handle makes the delete fail outright. These directories live outside `WORKPAL_WORKSPACES_ROOT`, so nothing else reclaimed them and whatever the end-of-run removal missed accumulated forever. Every GC cycle now sweeps the temp base. Liveness is decided by the directory's `.task_lock` — the same OS advisory lock an env root uses, which the kernel releases when the holding process dies — not by age: a directory still in use is never removed however old it is, including one owned by a different daemon sharing the same temp base, and a directory whose owner is gone is removed on the next cycle however new it is. Directories left by a daemon predating that lock carry no lock file, so nothing can be proven about them and age is the only signal available. Reclaiming those is an operator's explicit decision: `WORKPAL_GC_TASK_TEMP_LEGACY_TTL` defaults to `0`, which leaves them in place. Set it to a duration only once you know no pre-lock daemon is still running tasks on this machine — a task may legitimately run for weeks (there is no default agent timeout), a daemon on another profile can still be on the old binary, and every daemon on the machine shares one temp base, so a TTL here can delete a `TMPDIR` that is still in use. Each GC cycle logs how many such directories it left alone. Even with a TTL set, a directory holding no task content is never reclaimed on age — an old empty leftover, or a shell left by a daemon that died between creating the directory and publishing its lock — because holding no content is exactly what a directory currently being published looks like, and deleting one of those would take the `TMPDIR` of a task that is starting. Those shells are a few bytes each. Only entries carrying the `workpal-task-` prefix are ever considered — the temp base itself is usually shared with other programs — and a directory this sweep cannot read is never touched.

Configured patterns are basename-only — entries containing `/` or `\` are silently dropped — and `.git` subtrees are never descended into. The managed Codex cache is matched by its exact relative path, so a repository's own `.sandbox-bin` is not removed unless an operator explicitly adds that basename to `WORKPAL_GC_ARTIFACT_PATTERNS`. The default list (`node_modules`, `.next`, `.turbo`) is intentionally narrow; extend it per deployment if your repos consistently produce other regenerable directories (for example, `WORKPAL_GC_ARTIFACT_PATTERNS=node_modules,.next,.turbo,target,__pycache__`). To disable artifact cleanup entirely, including the managed Codex cache, set `WORKPAL_GC_ARTIFACT_TTL=0`.

`workpal daemon disk-usage` reports the `.repos` footprint on its own line rather than folding it into the per-task totals — every task in a workspace checks out from that shared cache, so attributing it to individual task directories would double-count it. Note that the repo cache is reclaimed on the schedule above and not by any per-issue status change, so it is normal for it to persist after every task directory is gone.

Agent-specific overrides:

| Variable | Description |
|----------|-------------|
| `WORKPAL_CLAUDE_PATH` | Custom path to the `claude` binary |
| `WORKPAL_CLAUDE_MODEL` | Override the Claude model used |
| `WORKPAL_CLAUDE_ARGS` | Default extra arguments for Claude Code runs |
| `WORKPAL_ANTIGRAVITY_PATH` | Custom path to the `agy` binary |
| `WORKPAL_ANTIGRAVITY_MODEL` | Override the Antigravity model used |
| `WORKPAL_CODEBUDDY_PATH` | Custom path to the `codebuddy` binary |
| `WORKPAL_CODEBUDDY_MODEL` | Override the CodeBuddy model used |
| `WORKPAL_CODEBUDDY_ARGS` | Default extra arguments for CodeBuddy runs |
| `WORKPAL_CODEARTS_PATH` | Custom path to the `codearts` launcher or binary |
| `WORKPAL_CODEARTS_MODEL` | Override the CodeArts model used |
| `WORKPAL_DEVECO_PATH` | Custom path to the `deveco` binary |
| `WORKPAL_DEVECO_MODEL` | Override the DevEco Code model used |
| `WORKPAL_CODEX_PATH` | Custom path to the `codex` binary |
| `WORKPAL_CODEX_MODEL` | Override the Codex model used |
| `WORKPAL_CODEX_ARGS` | Default extra arguments for Codex runs |
| `WORKPAL_COPILOT_PATH` | Custom path to the `copilot` binary |
| `WORKPAL_COPILOT_MODEL` | Override the Copilot model used (note: GitHub Copilot routes models through your account entitlement, so this may not be honoured) |
| `WORKPAL_OPENCODE_PATH` | Custom path to the `opencode` binary |
| `WORKPAL_OPENCODE_MODEL` | Override the OpenCode model used |
| `WORKPAL_OPENCLAW_PATH` | Custom path to the `openclaw` binary |
| `WORKPAL_OPENCLAW_MODEL` | Select the registered OpenClaw agent ID used by default; the agent's `runtime_config.model_override` persistently overrides its underlying model for all newly claimed runs until changed or cleared |
| `WORKPAL_OPENCLAW_CLI_TIMEOUT` | Deadline for each `openclaw config ...` call during task preparation (default 30s; accepts `45s` or `45`). Raise it when the local CLI is slow to start; the daemon also reads it from `backends.openclaw.cli_timeout` in the CLI config |
| `WORKPAL_HERMES_PATH` | Custom path to the `hermes` binary |
| `WORKPAL_HERMES_MODEL` | Override the Hermes model used |
| `WORKPAL_PI_PATH` | Custom path to the `pi` binary |
| `WORKPAL_PI_MODEL` | Override the Pi model used |
| `WORKPAL_CURSOR_PATH` | Custom path to the `cursor-agent` binary |
| `WORKPAL_CURSOR_MODEL` | Override the Cursor Agent model used |
| `WORKPAL_KIMI_PATH` | Custom path to the `kimi` binary |
| `WORKPAL_KIMI_MODEL` | Override the Kimi model used |
| `WORKPAL_REASONIX_PATH` | Custom path to the `reasonix` binary |
| `WORKPAL_REASONIX_MODEL` | Override the Reasonix model used |
| `WORKPAL_DIM_PATH` | Custom path to the `dim` binary |
| `WORKPAL_DIM_MODEL` | Override the Dim model used |
| `WORKPAL_DEVIN_PATH` | Custom path to the `devin` binary |
| `WORKPAL_DEVIN_MODEL` | Override the Devin model used |
| `WORKPAL_KIRO_PATH` | Custom path to the `kiro-cli` binary |
| `WORKPAL_KIRO_MODEL` | Override the Kiro model used |
| `WORKPAL_QODER_PATH` | Custom path to the `qodercli` binary |
| `WORKPAL_QODER_MODEL` | Override the Qoder model used |
| `WORKPAL_QODERCLICN_PATH` | Custom path to the `qoderclicn` binary |
| `WORKPAL_QODERCLICN_MODEL` | Override the Qoder CN model used |
| `WORKPAL_TRAECLI_PATH` | Custom path to the `traecli` binary |
| `WORKPAL_TRAECLI_MODEL` | Override the Trae model used (a model id from your logged-in traecli catalog, e.g. `Doubao-Seed-2.1-Pro`) |
| `WORKPAL_GROK_PATH` | Custom path to the `grok` binary (defaults to `grok` on PATH; often `~/.grok/bin/grok`) |
| `WORKPAL_GROK_MODEL` | Override the Grok model used (e.g. `grok-4.5`) |
| `WORKPAL_QWEN_PATH` | Custom path to the `qwen` binary |
| `WORKPAL_QWEN_MODEL` | Override the Qwen Code model used |
| `WORKPAL_QWEN_ARGS` | Daemon-wide extra Qwen arguments (POSIX shellword parsing; managed protocol flags are filtered) |
| `WORKPAL_AMP_PATH` | Custom path to the `amp` executable |
| `WORKPAL_AMP_MODEL` | Amp mode (such as `high`); empty uses Amp's default |
| `WORKPAL_AMP_ARGS` | Supported extra Amp options, e.g. `--features fast`; protocol, executor, prompt and mode overrides are filtered |
| `WORKPAL_DROID_PATH` | Custom path to the native `droid` executable |
| `WORKPAL_DROID_MODEL` | Droid model ID; defaults to Droid's own configuration |
| `WORKPAL_DROID_ARGS` | Daemon-wide Droid arguments, e.g. `--reasoning-effort high`; managed protocol, prompt, session, and working-directory flags are filtered |
| `WORKPAL_QWENPAW_PATH` | Custom path to the `qwenpaw` binary |
| `WORKPAL_QWENPAW_ARGS` | Daemon-wide extra QwenPaw arguments (POSIX shellword parsing; managed protocol flags are filtered) |
| `WORKPAL_MCODE_PATH` | Custom path to the `mcode` binary |
| `WORKPAL_DSH_PATH` | Custom path to the `dsh` binary |
| `WORKPAL_DSH_MODEL` | Override the DeepSeek Harness model used (a model id from the dsh catalog, e.g. `deepseek-official/deepseek-chat`) |

If a previously generated `~/.workpal/hooks` wrapper is first on `PATH` and calls the same command name again, the daemon skips that hooks directory during built-in agent discovery and records the real binary path behind it. If your interactive shell still recurses when you run `claude`, `codex`, or `hermes` manually, remove the hooks entry from your shell startup file or replace the wrapper body with an absolute `exec /path/to/real-binary "$@"`.

The daemon launches Qoder and Qoder CN as `qodercli --yolo --acp` and `qoderclicn --yolo --acp`, respectively, matching their ACP “bypass permissions” mode so tool runs do not block on interactive approval in headless runs.
The daemon launches Qwen Code as `qwen -p <prompt> --output-format stream-json`. It writes the task brief to `QWEN.md`; when an agent has managed `mcp_config`, the daemon writes a 0600 per-run JSON file and passes it through `--mcp-config <path>`, then removes it after the process exits. A null config preserves Qwen Code native MCP settings.

#### `mcp_config` on ACP runtimes

ACP-family runtimes — Hermes, Kimi, Kiro, Grok, Qoder, Reasonix, Trae, QwenPaw, MiniMax Code, Dim, and any custom runtime profile whose `protocol_family` is one of them — receive MCP servers **over the ACP session protocol**, not through a config file. The daemon translates the agent's `mcp_config` into ACP's `McpServer` array and sends it with `session/new`, and again with that runtime's resume request (`session/resume` on Hermes, Kimi, Qoder and Reasonix; `session/load` on Kiro, Grok, Trae, QwenPaw and Dim) so a resumed task keeps the same tools. MiniMax Code 0.1.2 advertises no session-loading capability, so a later run falls back to a fresh session.

Nothing is written to the runtime's own config file, and the runtime's own file is not read or merged. `~/.hermes/…`, `~/.jcode/mcp.json` and the like stay untouched; an agent's servers travel with its tasks instead of being installed per machine.

Two consequences are worth knowing before debugging a missing MCP tool:

- **`mcp_config` must use the canonical envelope**, `{"mcpServers": {"<name>": {…}}}`. Runtime-native config files that nest servers under `servers`, `mcp`, or `mcp_servers` are stored as-is but yield no servers; the daemon logs a warning naming the key it found. Entries themselves use the Claude-style shape (`command`/`args`/`env` for stdio, `url`/`headers`/`type` for remote).
- **Remote transports depend on what the runtime declares.** ACP v1 requires an omitted capability to be treated as unsupported, so `http` and `sse` entries are dropped with a warning unless the `initialize` response declares `agentCapabilities.mcpCapabilities` with that transport set to true. The built-in Hermes runtime is a verified exception: it declares no `mcpCapabilities` yet accepts both transports, so remote entries are still forwarded to it. That exception covers the Hermes binary only — a custom runtime profile with `protocol_family: hermes` runs a different implementation and keeps the standard rule. Stdio is never gated.

If a configured server produces no tools, check the daemon log for those warnings first, then confirm the runtime itself exposes the server's tools to the model — some ACP adapters apply their own tool-profile filtering after connecting.


The daemon launches QwenPaw as `qwenpaw acp --workspace <per-task dir>`. It writes the task brief to `AGENTS.md`, and materialises the run's bound skills into `<per-task dir>/skills/` plus a `skill.json` manifest, so QwenPaw discovers them through its own workspace skill discovery. `acp` and `--workspace` are reserved: `custom_args` cannot override them. QwenPaw is the one runtime with no `WORKPAL_QWENPAW_MODEL`: its `session/set_model` writes to a shared, persistent agent config rather than the session, so Workpal never sends it a model and leaves that choice to QwenPaw's own configuration.

The daemon launches MiniMax Code as `mcode acp`, writes the task brief to `AGENTS.md`, and injects bound skills under `.minimax/skills/`. MCode owns model selection and currently advertises `loadSession: false`; Workpal therefore starts a fresh MCode session when a later run cannot load the saved session.

#### Hermes agent memory

On Windows, detected Hermes versions 0.22 and later use a daemon-owned foreground
gateway for each isolated task home. The daemon waits for its startup reservation
before launching ACP, which performs the readiness handshake. The gateway and its
tool descendants remain in a Windows job object and are terminated on task cleanup
or cancellation; agent jobs do not permit breakaway. Other platforms and older or
unrecognized Hermes versions retain their existing ACP startup behavior.

Hermes discovers skills only from its own home, so binding Workpal skills to a Hermes agent makes the daemon build a per-task `HERMES_HOME` overlay for that agent. The agent's long-term memory (`memories/`) does **not** live inside that task-scoped overlay: it is linked to a persistent store at

```
<profile dir>/hermes-state/<agent-id>/<hermes-profile>/
```

so the same agent keeps its memory across tasks and issues. `<hermes-profile>` is the profile the agent resolves to (`default`, a named profile from `-p/--profile` or `active_profile`, or a hash for an out-of-tree custom `HERMES_HOME`) — pointing an agent at a different profile gives it a different memory line, matching Hermes' own "a profile is an isolated instance" model.

Consequences worth knowing:

- **Memory is agent-scoped but runtime-local.** One agent's memory is never visible to another, and the user's own `~/.hermes/memories` is never read or written. The store lives in this runtime's Workpal profile directory, so it does **not** follow the agent to another machine — an agent that runs on two runtimes has a separate memory line on each. Everything else in the home — auth, config, plugins — is still shared from the user's real home by symlink, so the agent does not need its own login.
- **To carry existing local memory in**, copy it into the store once: `cp -R ~/.hermes/memories/. "<profile dir>/hermes-state/<agent-id>/default/"`. To wipe an agent's memory, delete that directory.
- **Conversation history is covered too, in a separate store.** Hermes keeps every ACP session in `<HERMES_HOME>/state.db`, which the overlay links to a per-conversation store at `<profile dir>/hermes-sessions/<agent-id>/<hermes-profile>/<issue-id | chat_\<chat-session-id\>>/`, so a follow-up turn resumes the actual transcript. The shard is per conversation rather than per agent on purpose: tasks of one conversation run one after another, so a shard has a single writer at a time, while two issues never share a database. A host that cannot create the link (Windows without symlink privileges) keeps the database task-local instead, untouched — the link is proven creatable before anything is moved, and a copy is never used, because a copied SQLite database would absorb the turn's writes into a file the next task discards.
- **Concurrent tasks of one agent are last-writer-wins.** Hermes rewrites its memory files whole, so two tasks writing memory at the same time can overwrite each other.
- **Every Hermes agent gets the overlay in practice**, so every one of them gets a persistent memory store. The daemon builds the overlay only when a task carries skills, but the server appends Workpal's built-in skills to every agent's skill set (`LoadAgentSkillBundles`), so that list is never empty — leaving an agent's own skill list empty does not opt out of the overlay, and is not a way to keep using the host's `~/.hermes/memories`.

`WORKPAL_CLAUDE_ARGS`, `WORKPAL_CODEX_ARGS`, `WORKPAL_CODEBUDDY_ARGS`, `WORKPAL_QWEN_ARGS`, and `WORKPAL_QWENPAW_ARGS` are parsed with POSIX shellword quoting, so values such as `--model "gpt-5.1 codex" --sandbox read-only` are split like a shell command line. Agent arguments are applied in this order: hardcoded Workpal defaults, daemon-wide env defaults, then per-agent `custom_args` from the task.

### Self-Hosted Server

When connecting to a self-hosted Workpal instance, the easiest approach is:

```bash
# One command — configures for localhost, authenticates, starts daemon
workpal setup self-host

# Or for on-premise with custom domains:
workpal setup self-host --server-url https://api.example.com --app-url https://app.example.com
```

Or configure manually:

```bash
# Set URLs individually
workpal config set server_url http://localhost:8080
workpal config set app_url http://localhost:3000

# For production with TLS:
# workpal config set server_url https://api.example.com
# workpal config set app_url https://app.example.com

workpal login
workpal daemon start
```

### Profiles

Profiles let you run multiple daemons on the same machine — for example, one for production and one for a staging server.

```bash
# Set up a staging profile
workpal setup self-host --profile staging --server-url https://api-staging.example.com --app-url https://staging.example.com

# Start its daemon
workpal daemon start --profile staging

# Default profile runs separately
workpal daemon start
```

Each profile gets its own config directory (`~/.workpal/profiles/<name>/`), daemon state, health port, and workspace root. Daemon state means that profile's own `daemon.log`, `daemon.err.log`, `daemon.pid`, and `daemon.port` live in that directory too — see [Start](#start) for the layout, and pass `--profile <name>` to `daemon status` / `daemon logs` to act on it. The daemon normally uses the profile-derived health port. If the OS refuses that port, it binds an available loopback port and records the actual port in `daemon.port` for lifecycle commands. The record is valid only while its daemon is alive; do not edit it to configure a port.

## Workspaces

### Working with multiple workspaces

Every command runs against a single workspace. The CLI resolves which one in this order (highest priority first):

1. `--workspace-id <id>` flag on the command
2. `WORKPAL_WORKSPACE_ID` environment variable
3. The default workspace stored in your current profile (set by `workpal workspace switch` or `workpal login`)

`workpal workspace switch <id|slug>` is the day-to-day way to change the default workspace. For scripting and headless setups where you don't want any stored state, prefer the `--workspace-id` flag or the env variable. `workpal config set workspace_id <id>` is the low-level equivalent of `switch` (it writes the same setting but skips the access check).

If you need full isolation between organizations or accounts — separate tokens, separate daemons, separate config dirs — use `--profile <name>` instead. Each profile keeps its own default workspace.

### List Workspaces

```bash
workpal workspace list
workpal workspace list --full-id
workpal workspace list --output json
```

The current default workspace is marked with `*`. Table output shows short UUID prefixes — pass `--full-id` when you need the canonical UUIDs.

### Switch Default Workspace

```bash
workpal workspace switch <workspace-id>
workpal workspace switch <slug>
```

Verifies you have access to the workspace, then sets it as the default for the current profile. Subsequent commands without `--workspace-id` and `WORKPAL_WORKSPACE_ID` target this workspace. Pair `--profile` if you want to change a non-default profile's workspace.

### Get Details

```bash
workpal workspace get <workspace-id>
workpal workspace get <workspace-id> --output json
```

Passing no `<workspace-id>` resolves to the current default workspace, so `workpal workspace get` doubles as "what workspace am I on?".

### List Members

```bash
workpal workspace member list <workspace-id>
```

## Issues

### List Issues

```bash
workpal issue list
workpal issue list --status in_progress
workpal issue list --priority urgent --assignee "Agent Name"
workpal issue list --assignee-id 5fb87ac7-23b5-4a7a-81fa-ed295a54545d
workpal issue list --full-id
workpal issue list --limit 20 --output json
workpal issue list --status todo --sort position       # board order (the default)
workpal issue list --sort created_at --direction desc  # newest first
workpal issue list --output json --fields=id,title,status,priority  # narrow the JSON payload
workpal issue list --output json --resolve-properties  # property names beside the ids
```

Table output shows a routable issue `KEY` such as `MUL-123`; copy that key into follow-up commands like `issue get`, `issue comment list`, `issue status`, or `--parent`. Add `--full-id` when you need canonical UUIDs. Available filters: `--status`, `--priority`, `--assignee` / `--assignee-id`, `--project`, `--metadata`, `--property`, plus `--limit` and `--offset` for paging. Use `--assignee-id <uuid>` for unambiguous filtering when names overlap.

If the server cannot count the matching issues, the list request fails with `failed to count issues` instead of returning the page length as a fabricated total. Successful response fields are unchanged. This trades availability of a partial page for an explicit failure that callers can retry.

`--fields` (JSON output only) whitelists which top-level issue keys come back — pass a comma-separated list such as `--fields=id,title,status,priority`. Omit it for the full issue object, unchanged from before this flag existed. Filtering happens client-side after the CLI fetches the full response, so this shrinks CLI output size and agent context cost — not network transfer or server-side work. Field names are the real API keys, not table-display labels — assignee is `assignee_type`/`assignee_id` rather than a single `assignee` field. An unknown name is rejected up front with the valid list rather than silently dropped. Has no effect on `--output table`.

Results come back in board order (`position`, ascending) by default. Pass `--sort` to change the column (`position`, `title`, `created_at`, `start_date`, `due_date`, `priority`, or `property:<name-or-id>` for a custom property — select properties order by option order, and issues without the property sort last) and `--direction asc|desc` to flip the order. `position` is always ascending (it is the manual drag order), so `--direction` is rejected when `--sort` is `position` or omitted — use it only with `title`, `created_at`, `start_date`, `due_date`, `priority`, or a `property:` sort.

One call returns one page. `--limit` is the page size, 1 to 100 (the server returns at most 100 issues per request), and `--offset` is how many issues to skip. A limit outside 1 to 100 or a negative offset is rejected rather than quietly clamped. In table mode a line on stderr says when you are looking at a page of a larger set (`Showing 1-50 of 2706 issues. Next page: --offset 50`). It prints whenever the JSON `has_more` described below would be true or `--offset` is above zero, and stays silent otherwise. The `of N` is dropped when the server's count cannot be trusted (`Showing issues 1-100. Next page: --offset 100`), for the reasons below.

With `--output json` the envelope carries `total`, `limit`, `offset` and `has_more`. `limit` and `offset` echo the request, so `limit` holds steady across a walk and `offset` is the one you passed. The number of issues in this page is `issues | length`, and that is what to advance `--offset` by: it equals `limit` on a full page and stays right on any page that comes back shorter. An empty page always reports `has_more: false`. `total` cannot end a walk on its own: when the server's count query fails it reports the size of the page it just returned, and a newer backend may drop the field. So a full page reports `has_more: true` whenever `total` is missing or no larger than the page itself. That rule means a list that fills exactly one page costs one extra request that comes back empty; the alternative is a walk that ends one page in whenever the count is unhealthy. To walk a whole list, sort by `created_at` (`--sort created_at --direction asc`): the default `position` order is re-ranked by board drags and status changes, so pages can shift under a walk. Sorting by `created_at` keeps them still, but no offset walk is a consistent snapshot while others are writing.

Use `--metadata key=value` (repeatable; combined with AND) to filter by per-issue metadata. The value is JSON-parsed: `true`/`false` become bool, numbers become numbers, anything else is a string. Wrap as `'"42"'` to force a string when the value would otherwise sniff as a number:

```bash
workpal issue list --metadata pipeline_status=waiting_review
workpal issue list --metadata pr_number=482 --metadata is_blocked=true
```

Use `--property "Name=Value"` (repeatable; one member per flag) to filter by custom property. Names and select option values are case-insensitive and resolve to ids; repeating the same property matches any of its members, different properties must all match. Values are option names or ids (select types), `true`/`false` (checkbox), a member name, email, or id (actor types), or the stored value itself for `text`, `url`, `number`, and `date` (`YYYY-MM-DD`). The reserved value `__none__` matches issues where the property is unset:

```bash
workpal issue list --property "Impact=High" --property "Impact=Medium"
workpal issue list --property "Impact=__none__" --status in_review
workpal issue list --property "Score=42" --property "Ship Date=2026-08-28"
```

Comparisons go in the same flag. `number` takes `>`, `>=`, `<` and `<=`; `date` takes `>` (after) and `<` (before); `text` and `url` take `~=` (contains, case-insensitive, matched exactly as typed). Quote the flag so the shell does not read `<` and `>` as redirection:

```bash
workpal issue list --property "Score>=3" --property "Impact=High"
workpal issue list --property "Ship Date<2026-09-01" --status todo
workpal issue list --property "Notes~=follow up"
```

A comparison on a type that cannot honour it is rejected with an error naming the type. So is `!=` (the server has no not-equal filter), and so are `>=` and `<=` on a date: the server only compares dates strictly, and the error names the strict form to use instead. Repeating a property ORs its members, so `"Score>1"` plus `"Score<10"` is not a range. A property whose name contains `=`, `<`, `>`, `!` or `~` has to be given by its UUID.

In JSON output, `properties` is a map from definition id to the stored value: an option id for `select`, a list of option ids for `multi_select`, a `member:<uuid>` reference for the actor types, and the value itself otherwise. Pass `--resolve-properties` to replace that map with the rows `issue property list` prints, one per set property, in catalog order: `property_id`, `name`, `type`, the stored `value`, a human `display`, `display_values` (the per-item names of a `multi_select` or `multi_actor` value) and `archived` when the definition is archived. Archived definitions still resolve, since their values stay on the issue. An option that is no longer in the definition, or a member who has left the workspace, keeps its raw id in `display`. The flag adds at most two requests: the catalog, shared with `--property` and `--sort property:`, and the member list, fetched only when an actor `--property` filter or an actor value on the page needs it and shared between the two. If either request fails the command fails rather than printing ids. In JSON output it combines with `--fields` only when that list keeps `properties`; a `--fields` list without it is rejected rather than resolving a key the same command would delete. The flag has no effect on `--output table`, where it and `--fields` are both ignored and neither is rejected.

```bash
workpal issue list --output json --resolve-properties | jq '.issues[] | {identifier, properties: [.properties[]? | {name, display}]}'
```

### Get Issue

```bash
workpal issue get <id>
workpal issue get <id> --output json
workpal issue get <id> --resolve-properties   # property names beside the ids, as in issue list
```

### Create Issue

```bash
workpal issue create --title "Fix login bug" --description "..." --priority high --assignee "Lambda"
workpal issue create --title "Fix login bug" --assignee-id 5fb87ac7-23b5-4a7a-81fa-ed295a54545d
```

Flags: `--title` (required), `--description`, `--status`, `--priority`, `--assignee` / `--assignee-id`, `--parent`, `--project`, `--due-date`. Pass `--assignee-id <uuid>` (mutually exclusive with `--assignee`) when scripting against the IDs returned by `workpal workspace member list --output json` / `workpal agent list --output json`.

### Update Issue

```bash
workpal issue update <id> --title "New title" --priority urgent
workpal issue update <id> --position 4.5
workpal issue update <id> --attachment revised.png
```

`--position` sets the raw ordering value within the board column (lower sorts first). For relative moves, `issue reorder` is easier because it works out the value for you.
`--attachment` uploads a local file and appends its Markdown reference to the end of the issue description. Repeat the flag to attach multiple files. To replace an existing image, also use `--description-file` to remove the old reference from the description.

### Delete Issue

```bash
workpal issue delete <id>                 # prompts before deleting
workpal issue delete <id> --yes           # no prompt
workpal issue delete MUL-101 MUL-102 --yes --output json
```

Deletion is permanent and removes the issue's comments and attachments, cancels its in-flight runs, fails linked autopilot runs, clears duplicate marks that pointed at it, and detaches its child issues without deleting them.

Ids may be issue keys or full UUIDs. Every id is resolved with a read before the prompt, full UUIDs included, so an unknown, stale or invisible issue aborts the whole command instead of leaving a partial batch; several ids go to one batch request whose permission check covers the whole selection.

`--yes` skips the confirmation. Without it the command reads stdin; if stdin closes without an answer (a non-interactive run) the command fails without deleting, while answering `n` declines and deletes nothing.

With `--output json`, one id prints `{"id": "<uuid>", "deleted": true}` and several print `{"ids": ["<uuid>", ...], "deleted": true}`, always with canonical UUIDs whatever spelling was passed. If the server deletes only part of a batch, the command prints `{"ids": ["<uuid>", ...], "deleted": false, "deleted_count": N}` and exits non-zero.

### Reorder Issue

Move an issue within its current status column. The new ordering value is computed the same way the board's drag-and-drop computes it, so the CLI and UI agree on where the issue lands.

```bash
workpal issue reorder <id> --top              # top of its status column
workpal issue reorder <id> --bottom           # bottom of its status column
workpal issue reorder <id> --before <other>   # directly above another issue in the same column
workpal issue reorder <id> --after  <other>   # directly below another issue in the same column
```

Pick exactly one of `--top`, `--bottom`, `--before`, or `--after`. Reorder stays inside the issue's current column, so `--before` / `--after` must name an issue in that same column. To move an issue to a different column, change its status first with `issue status`, then reorder within the new column.

Reorder reads the project-scoped column before computing the new position. With older servers that omit the total or substitute the page length after a failed count, it continues to an empty page instead of trusting that count. This may cost one extra request. A failed page request, malformed issue, or repeated issue aborts the operation before a position is written. These checks do not provide a consistent snapshot across concurrent edits.

### Assign Issue

```bash
workpal issue assign <id> --to "Lambda"
workpal issue assign <id> --to-id 5fb87ac7-23b5-4a7a-81fa-ed295a54545d
workpal issue assign <id> --unassign
```

Pass `--to-id <uuid>` to assign by canonical UUID (mutually exclusive with `--to`); useful when names overlap across members and agents.

### Change Status

```bash
workpal issue status <id> in_progress
```

Built-in statuses: `backlog`, `todo`, `in_progress`, `in_review`, `done`, `blocked`,
`cancelled`. A workspace can define custom statuses on top of these; their keys are
shown in **Settings → Issue Statuses**, and passing an unknown value returns the full
list.

To cancel an issue because it duplicates another, mark it so the original lists it:

```bash
workpal issue status <id> cancelled --duplicate-of <original>
```

`--duplicate-of` takes an issue key or full UUID and requires status `cancelled`.
`issue update <id> --duplicate-of <original>` does the same, but cannot be combined with
description or attachment changes. Moving the issue to any other status removes the mark.

### Comments

```bash
# List comments — flat timeline, chronological. Hard cap of 2000 rows; on
# long-running issues prefer one of the thread-aware reads below to keep
# context windows tight.
workpal issue comment list <issue-id>

# Single thread (root + every descendant). Anchor may be the root itself
# or any reply inside the thread — the server walks up to the root.
workpal issue comment list <issue-id> --thread <comment-id>

# Single thread, capped to the N most recent replies. The thread root is
# always included (even with --tail 0), so an agent landing on a long
# thread keeps the "what is this about" context without dragging hundreds
# of replies into its prompt.
workpal issue comment list <issue-id> --thread <comment-id> --tail 30

# Scroll older replies inside the same thread. --before / --before-id are
# the reply cursor that the previous response emitted on stderr as
# `Next reply cursor: --before <ts> --before-id <reply-id>`.
workpal issue comment list <issue-id> --thread <comment-id> --tail 30 \
    --before <ts> --before-id <reply-id>

# Most recently active threads (root + every descendant), grouped by
# thread. Returns N complete conversational arcs, oldest-active first so
# the freshest thread sits closest to "now" in an agent prompt.
workpal issue comment list <issue-id> --recent 10

# Scroll older threads. Under --recent, --before / --before-id are a
# THREAD cursor (thread last_activity_at + root id), emitted on stderr as
# `Next thread cursor: --before <ts> --before-id <root-id>`.
workpal issue comment list <issue-id> --recent 10 \
    --before <ts> --before-id <root-id>

# Incremental polling. Combines with --thread or --recent; filters out
# replies created on or before <ts> from the page (the thread root is
# exempt so the agent always gets context).
workpal issue comment list <issue-id> --thread <comment-id> --tail 30 \
    --since <RFC3339-timestamp>

# Add a comment
workpal issue comment add <issue-id> --content "Looks good, merging now"

# Reply to a specific comment
workpal issue comment add <issue-id> --parent <comment-id> --content "Thanks!"

# Add the comment to an agent's running turn instead of queueing a
# follow-up run (--steer is repeatable; --steer-active picks every running
# agent you may steer). You may steer an agent exactly when your comment could
# start it; an agent never steers itself and adds at most 3 messages to one
# run. Prints per run whether it was steered.
workpal issue comment add <issue-id> --content-file note.md --steer <run-id>

# Delete a comment
workpal issue comment delete <comment-id>
```

**`--before` / `--before-id` semantics depend on the paging mode**, by
design — same flag, different scope:

| Mode | What the cursor walks | stderr label |
| --- | --- | --- |
| `--recent N` | Older *threads* (last_activity_at, root_id) | `Next thread cursor` |
| `--thread <id> --tail N` | Older *replies* inside that thread (created_at, id) | `Next reply cursor` |

Outside those two modes (`--thread` without `--tail`, or no `--thread`
and no `--recent`) the cursor flags are rejected so they cannot silently
no-op. The server emits the cursor headers (`X-Workpal-Next-Before` /
`X-Workpal-Next-Before-Id`) only when an older page actually exists —
exact-boundary pages (e.g. `--tail 3` on a thread with exactly 3
replies) intentionally return no cursor so callers stop paginating.

When `--since` is combined with `--recent` or `--thread --tail`, the
server additionally suppresses the cursor once the cursor target itself
is older than `since`. Older pages walk strictly older rows, so they
cannot satisfy `> since` either — emitting a cursor there would just
hand back root-only pages until the caller reaches the start of the
thread / issue. Incremental polling stops at the first page whose
cursor target falls before the watermark.

### Metadata

Per-issue metadata is a small KV map agents use to track pipeline state (PR number, pipeline status, waiting_on, ...). Keys match `^[a-zA-Z_][a-zA-Z0-9_.-]{0,63}$`, values are primitives (string / number / bool), max 50 keys per issue, blob capped at 8KB.

The bar for writing is high: pin a value only when it is materially important to the issue AND likely to be re-read by future runs on this same issue (the PR URL, the deploy URL, what we're blocked on). Most runs write zero new keys — that's the expected case. Don't pin runtime bookkeeping like `attempts`, single-run investigation notes, large logs, secrets/tokens, or description/comment copies — see the agent runtime prompt for the full anti-pattern list.

```bash
# List every key on an issue
workpal issue metadata list <issue-id>

# Read a single key
workpal issue metadata get <issue-id> --key pipeline_status

# Write a single key — value auto-typed (true/false → bool, numbers → number, else string)
workpal issue metadata set <issue-id> --key pipeline_status --value waiting_review
workpal issue metadata set <issue-id> --key pr_number --value 482
workpal issue metadata set <issue-id> --key is_blocked --value true

# Force a specific type when sniffing would pick the wrong one
workpal issue metadata set <issue-id> --key code --value 42 --type string

# Remove a key
workpal issue metadata delete <issue-id> --key pipeline_status
```

All writes are single-key atomic — concurrent agents writing different keys do not lose each other's updates. To query, use `workpal issue list --metadata key=value` (see *List Issues* above).

### Subscribers

```bash
# List subscribers of an issue
workpal issue subscriber list <issue-id>

# Subscribe yourself to an issue
workpal issue subscriber add <issue-id>

# Subscribe another member or agent by name
workpal issue subscriber add <issue-id> --user "Lambda"

# Unsubscribe yourself
workpal issue subscriber remove <issue-id>

# Unsubscribe another member or agent
workpal issue subscriber remove <issue-id> --user "Lambda"
```

Subscribers receive notifications about issue activity (new comments, status changes, etc.). Without `--user`, the command acts on the caller.

### Execution History

```bash
# List all execution runs for an issue
workpal issue runs <issue-id>
workpal issue runs <issue-id> --full-id
workpal issue runs <issue-id> --output json

# Only work in flight (queued / dispatched / running / waiting_local_directory)
workpal issue runs <issue-id> --active --output json

# ...and across the sub-issue family: the issue's parent (or itself, when it has
# no parent) plus every child of that parent, each row labelled with its issue.
# Answers "is another agent already working next to me?" before you start
# overlapping code or PR work. Advisory only — it reserves nothing.
#
# Returns a compact per-run row — task_id, issue_id, issue_identifier,
# issue_title, agent_id, status, created_at, started_at — not the full
# execution-log record. Follow a task_id with `issue run-messages` for detail.
#
# Ordered running-first, newest-first within a status, capped at 20 rows. When
# the cap truncates the answer the server sets X-Active-Runs-Truncated and the
# CLI warns on stderr, so a short list is never mistaken for a complete one.
workpal issue runs <issue-id> --siblings --output json

# View messages for a specific execution run
workpal issue run-messages <task-id>
workpal issue run-messages <short-task-id> --issue <issue-id>
workpal issue run-messages <task-id> --output json

# Incremental fetch (only messages after a given sequence number)
workpal issue run-messages <task-id> --since 42 --output json

# Aggregated token usage for an issue (sum across all its task runs)
workpal issue usage <issue-id>
workpal issue usage <issue-id> --output json
```

The `usage` command returns the aggregated token usage for an issue, summed across all of its task runs: input tokens, output tokens, cache read/write tokens, and the run count (`task_count`). It wraps `GET /api/issues/<id>/usage` — the same figures the issue detail view shows. Use `--output json` to feed billing/cost tooling.

The `runs` command shows all past and current executions for an issue, including running tasks. Table output uses short task UUID prefixes by default; pass `--full-id` to print canonical task UUIDs. The `run-messages` command accepts full task UUIDs directly; copied short task prefixes must be scoped with `--issue <issue-id>` so the CLI only checks that issue's runs. It shows the detailed message log (tool calls, thinking, text, errors) for a single run. Use `--since` for efficient polling of in-progress runs.

## Projects

Projects group related issues (e.g. a sprint, an epic, a workstream). Every project
belongs to a workspace and can optionally have a lead (member or agent).

### List Projects

```bash
workpal project list
workpal project list --status in_progress
workpal project list --output json
workpal project list --archived
```

Available filters: `--status`, `--archived` (only archived projects; they are hidden by default).

### Get Project

```bash
workpal project get <id>
workpal project get <id> --output json
```

### Create Project

```bash
workpal project create --title "2026 Week 16 Sprint" --icon "🏃" --lead "Lambda"
```

Flags: `--title` (required), `--description`, `--status`, `--icon`, `--lead`, `--start-date`, `--due-date`. Dates are calendar days (`YYYY-MM-DD`).

### Update Project

```bash
workpal project update <id> --title "New title" --status in_progress
workpal project update <id> --lead "Lambda"
workpal project update <id> --due-date 2026-04-15
```

Flags: `--title`, `--description`, `--status`, `--icon`, `--lead`, `--start-date`, `--due-date`. For the date flags, pass an empty string (e.g. `--start-date ""`) to clear the date.

### Change Status

```bash
workpal project status <id> in_progress
```

Valid statuses: `planned`, `in_progress`, `paused`, `completed`, `cancelled`.

### Archive and Restore

```bash
workpal project archive <id>
workpal project restore <id>
```

Archiving hides a project from lists and pickers and stops new issues from being
filed into it (HTTP 409 `project_archived`); existing issues stay editable.
Active autopilots that file into the project are paused, and restoring does not
resume them. Archiving is independent of status.

### Delete Project

```bash
workpal project delete <id>
```

### Associating Issues with Projects

Use the `--project` flag on `issue create` / `issue update` to attach an issue to a
project, or on `issue list` / `issue search` to filter issues by project:

```bash
workpal issue create --title "Login bug" --project <project-id>
workpal issue update <issue-id> --project <project-id>
workpal issue list --project <project-id>
workpal issue search "Login" --project <project-id>
```

## Setup

```bash
# One-command setup for Workpal Cloud: configure, authenticate, and start the daemon
workpal setup

# For local self-hosted deployments
workpal setup self-host

# Custom ports
workpal setup self-host --port 9090 --frontend-port 4000

# On-premise with custom domains
workpal setup self-host --server-url https://api.example.com --app-url https://app.example.com
```

`workpal setup` configures the CLI, opens your browser for authentication, and starts the daemon — all in one step. Use `workpal setup self-host` to connect to a self-hosted server instead of Workpal Cloud.

## Configuration

### View Config

```bash
workpal config show
```

Shows config file path, server URL, app URL, and default workspace.

### Set Values

```bash
workpal config set server_url https://api.example.com
workpal config set app_url https://app.example.com
workpal config set workspace_id <workspace-id>
```

`config set workspace_id <id>` is the low-level interface — it writes the value verbatim without checking that the workspace exists or that you have access. Prefer `workpal workspace switch <id|slug>` for day-to-day workspace changes; it does both checks before saving.

## Autopilot Commands

Autopilots are scheduled/triggered automations that dispatch agent tasks (either by creating an issue or by running an agent directly).

### List Autopilots

```bash
workpal autopilot list
workpal autopilot list --full-id
workpal autopilot list --status active --output json
```

Autopilot table IDs are short UUID prefixes; follow-up autopilot commands accept copied prefixes when they are unique in the current workspace. Use `--full-id` to print canonical UUIDs.

### Get Autopilot Details

```bash
workpal autopilot get <id>
workpal autopilot get <id> --output json   # includes triggers
```

In JSON output `triggers` is a **top-level key alongside `autopilot`**, not nested
inside it — the payload is `{"autopilot": {...}, "triggers": [...], "collaborators": [...]}`.
Read trigger ids with `jq '.triggers[].id'`, or use `autopilot trigger-list` below.
The table output shows only the autopilot's own fields, not its triggers.

### Create / Update / Delete

```bash
workpal autopilot create \
  --title "Nightly bug triage" \
  --description "Scan todo issues and prioritize." \
  --agent "Lambda" \
  --mode create_issue \
  --subscriber "Alice"

workpal autopilot create \
  --title "Weekly dependency audit" \
  --description "Audit dependencies for security updates." \
  --squad "Backend Squad" \
  --mode create_issue

workpal autopilot update <id> --status paused
workpal autopilot update <id> --squad-id <squad-uuid>
workpal autopilot update <id> --description "New prompt"
workpal autopilot update <id> --subscriber "Alice" --subscriber "Bob"
workpal autopilot update <id> --clear-subscribers
workpal autopilot delete <id>
```

`--mode` accepts `create_issue` (creates a new issue on each run and assigns it to the agent) or `run_only` (enqueues a direct agent task without creating an issue). `--agent` accepts either a name or UUID.
To assign a squad instead, use `--squad` (name or ID) or `--squad-id` (canonical UUID); the run goes to the squad's leader, and in `create_issue` mode the created issue is assigned to the squad. `--agent`, `--squad`, and `--squad-id` are mutually exclusive, and `create` requires one of them. On `update` they switch the assignee (sending `assignee_type` with `assignee_id`); an update without any of them leaves the current assignee untouched. Table output labels the assignee by type, e.g. `squad:Backend Squad`.
`--subscriber` accepts a workspace member name or user ID and may be repeated; on update it replaces the autopilot's subscriber template. Subscribers receive inbox notifications for issues created by a `create_issue` autopilot. Use `--clear-subscribers` to remove all autopilot subscribers.

### Manual Trigger

```bash
workpal autopilot trigger <id>            # Fires the autopilot once, returns the run
```

The command exits non-zero unless the run actually started (`issue_created` or
`running`). A `skipped` run — admission refused, runtime offline, quota
exhausted, a duplicate already in flight — dispatched nothing; its
`failure_reason` and `reason_code` are printed to stderr, and `--output json`
still writes the full run to stdout first.

Run as an agent (inside a task, or over A2A), the trigger is authorized as the
human that run acts for, not as the owner of the machine it executes on. That
human needs exactly the write access they would need to trigger it themselves —
and it is the only access checked: the machine's owner needs no grant on the
autopilot, only workspace membership. A run carrying no originator cannot
trigger at all, and says so rather than failing generically.

### Run History

```bash
workpal autopilot runs <id>
workpal autopilot runs <id> --limit 50 --output json
```

### Schedule Triggers

```bash
workpal autopilot trigger-list <autopilot-id>              # ids, kind, schedule, next run
workpal autopilot trigger-list <autopilot-id> --full-id    # canonical UUIDs
workpal autopilot trigger-add <autopilot-id> --cron "0 9 * * 1-5" --timezone "America/New_York"
workpal autopilot trigger-update <autopilot-id> <trigger-id> --enabled=false
workpal autopilot trigger-delete <autopilot-id> <trigger-id>
```

`trigger-list` is the way to obtain the `<trigger-id>` that `trigger-update`,
`trigger-delete` and `trigger-rotate-url` require. Like autopilot ids, trigger ids
may be passed as a short prefix as long as it is unique within that autopilot; use
`--full-id` to print canonical UUIDs. Webhook credentials are redacted in this
output — use `autopilot get <id> --output json --show-secrets` to reveal them.

The CLI exposes cron-based `schedule` triggers via `trigger-add`, and `webhook`
triggers via `trigger-add --kind webhook` plus `trigger-rotate-url`. The data model
also defines an `api` kind, which is not surfaced here.

### Webhook Event and Action Filters

Use a JSON file to configure the same event/action filters as the web UI:

```json
[
  {"event": "pull_request_review", "actions": ["submitted"]},
  {"event": "push"}
]
```

Save this array as `filters.json`, then create or update a webhook trigger:

```bash
workpal autopilot trigger-add <autopilot-id> --kind webhook --event-filters-file filters.json
workpal autopilot trigger-update <autopilot-id> <trigger-id> --event-filters-file filters.json
workpal autopilot get <autopilot-id> --output json
```

An event without `actions` (or with an empty actions array) accepts every action
for that event. Filters apply only to webhook triggers; schedule triggers reject
them. The server validates the filters using the same rules as UI submissions.

Omitting `--event-filters-file` on update preserves the saved filters. Replacing
filters requires a nonempty array; `null`, an empty array, unknown fields, and
malformed files are rejected. To explicitly remove filters and accept all events:

```bash
workpal autopilot trigger-update <autopilot-id> <trigger-id> --clear-event-filters
```

`--clear-event-filters` cannot be combined with `--event-filters-file`. Creation
without a filter file accepts all events. These flags configure existing event
and action matching; they do not add payload-field conditions.

## Other Commands

```bash
workpal version              # Show CLI version and commit hash
workpal update               # Update to latest version
workpal agent list           # List agents in the current workspace
```

## Output Formats

Most commands support `--output` with two formats:

- `table` — human-readable table (default for list commands)
- `json` — structured JSON (useful for scripting and automation)

```bash
workpal issue list --output json
workpal daemon status --output json
```

## Error Messages

The CLI funnels command errors returned to the top-level handler through a
single user-facing translation layer (`server/internal/cli/errors.go`) so that
what you see on the terminal is a short, actionable sentence rather than a raw
Go error, an HTTP status line, or an internal `resolve issue: ...` chain. (A
few commands print their own output or run deliberate fast probes — for example
`setup`'s short `/health` reachability check — and don't go through this
layer.) The underlying detail is still available on demand (see `--debug`).

### What you see

- **Friendly, single-line message.** Transport failures (timeout, DNS,
  connection refused, TLS) and HTTP status failures (401/403/404/409/400·422/
  429/5xx) are each rendered as one clear sentence with a next step — for
  example a timeout suggests checking the network or raising
  `WORKPAL_HTTP_TIMEOUT`, and a 401 tells you to run `workpal login`.
- **Server-provided validation messages are preserved.** For a 400/422 that
  carries a message from the server, that message is shown verbatim
  (`Invalid request: <server message>`); only when there is none do you get the
  generic "check your values / run with --help" hint.
- **No leaked internals by default.** Raw URLs, status lines, JSON bodies, and
  the internal verb chain are hidden unless you ask for them.

### Language

Messages default to **English**, matching the rest of the CLI's help output.
If a Chinese locale is detected in `LC_ALL`, `LC_MESSAGES`, or `LANG` (in that
precedence order), messages switch to **Chinese**. No flag is needed; set the
locale as usual:

```bash
LANG=zh_CN.UTF-8 workpal issue get MUL-9999   # 错误信息显示为中文
```

### Exit codes

The process exit code is tiered so scripts can branch on the failure class:

| Exit code | Meaning |
| --- | --- |
| `0` | success |
| `1` | generic / unclassified error |
| `2` | network error (timeout, DNS, connection refused, TLS, offline) |
| `3` | authentication / authorization (HTTP 401, 403) |
| `4` | not found (HTTP 404) |
| `5` | validation (HTTP 400, 422) |

```bash
workpal issue get MUL-9999
if [ $? -eq 4 ]; then echo "no such issue"; fi
```

### Seeing the full detail (`--debug`)

Pass the global `--debug` flag (or set `WORKPAL_DEBUG=1`) to print the complete
original error chain — the internal verb chain, the request method/path/status,
and the raw server body — underneath the friendly message. Use it when you need
to file a bug or understand exactly what the server returned:

```bash
workpal issue list --debug
WORKPAL_DEBUG=1 workpal issue update MUL-1234 --title "x"
```

### Request timeout

API requests use a default timeout of 30 seconds. Override it with
`WORKPAL_HTTP_TIMEOUT` when you are on a slow network; it accepts a Go duration
(`45s`, `2m`) or a plain number of seconds (`45`). Command-level deadlines are
always at least this value, so raising it takes effect across all commands.

```bash
WORKPAL_HTTP_TIMEOUT=60s workpal issue list
```

### Stall detection (skill commands)

A total-elapsed timeout punishes the transfer that is working: a large skill
arriving steadily over a slow link is cut off mid-body, while a dead connection
is held open for the full budget. The `skill` commands therefore fail on a lack
of *progress* instead:

- A read that receives no bytes for **15 seconds** fails immediately, reported
  as a stalled transfer rather than a timeout.
- A transfer that keeps producing bytes runs to completion, however long it
  takes, behind a loose **10 minute** whole-request ceiling.

Override the no-progress budget with `WORKPAL_HTTP_STALL_TIMEOUT` (same format
as `WORKPAL_HTTP_TIMEOUT`). If only `WORKPAL_HTTP_TIMEOUT` is set it applies on
this path too, as the no-progress budget — it keeps meaning "the longest I will
wait for this server", not "the longest this download may take".

```bash
WORKPAL_HTTP_STALL_TIMEOUT=45s workpal skill get <id>
```

Every other command still uses the total-elapsed timeout above. Stall detection
starts here because skill payloads are the largest responses the CLI reads; the
mechanism itself is not skill-specific.

### Skill payload size

`workpal skill get` and `workpal skill files list` return **metadata only** by
default — path, byte size and content hash for each file, plus the size and
hash of the SKILL.md body. Sizes are what tell you which file makes a skill
large, and they stay available no matter how large it gets.

Pass `--with-content` when you actually need the bodies:

```bash
workpal skill files list <id>                  # paths and sizes
workpal skill files list <id> --with-content   # bodies inlined
```

On the API, both endpoints accept `?include=content` and `?include=metadata`.
A request that sends neither still gets `content`, on both endpoints, so a
server upgrade never changes what an un-upgraded client receives — it is the
CLI that asks for the smaller shape.

### Custom runtime compatibility targets

Create custom Oh-My-Pi profiles with `workpal runtime profile create --runtime-type omp --command-name omp --display-name "Custom Oh-My-Pi"`.
The immutable `runtime_type` selects model discovery, skills paths, and launch behavior;
the server derives `protocol_family` (`pi` for `omp`). Custom command/path overrides and
fixed arguments still apply, and the runtime retains its custom-profile provenance.
Existing profiles and the legacy `--protocol-family` flag retain their original target.
