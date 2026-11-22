import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, matchesGlob } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { decideScopes, filters } from "./ci-scope.mjs";

// The filters use only literal paths, * and **; Node's matcher exercises those
// against realistic changes, including files removed or renamed by a PR.
function filterFiles(files) {
  return Object.fromEntries(Object.entries(filters).map(([scope, patterns]) => [
    scope, String(files.some((file) => patterns.some((pattern) => matchesGlob(file, pattern)))),
  ]));
}

for (const [name, files, selected] of [
  ["readme only", ["README.md"], []],
  ["stable release promotion", [".github/workflows/promote-release.yml"], ["scripts"]],
  ["release orchestration", [".github/workflows/release.yml"], ["scripts"]],
  ["release creation", [".goreleaser.yml"], ["scripts"]],
  ["docs only", ["apps/docs/content/docs/guide.mdx"], ["quality", "docs"]],
  ["docs test", ["apps/docs/lib/unrendered-bold.test.ts"], ["quality", "docs"]],
  ["web changelog", ["apps/web/features/landing/i18n/en.ts"], ["frontend", "quality"]],
  ["mobile UI", ["apps/mobile/app/index.tsx"], ["quality"]],
  ["migration only", ["server/go/migrations/999_example.up.sql"], ["backend", "sqlc"]],
  ["agent process code", ["server/go/pkg/agent/cursor_background.go"], ["backend", "runtime"]],
  ["daemon dependency", ["server/go/internal/skill/service.go"], ["backend", "runtime"]],
  ["process-group control", ["server/go/internal/daemon/processtree/controller_unix.go"], ["backend", "runtime", "processtree"]],
  ["process-group caller", ["server/go/internal/daemon/gc.go"], ["backend", "runtime"]],
  ["native test compilation dependency", ["server/go/pkg/db/generated/issues.sql.go"], ["backend", "sqlc", "runtime"]],
  ["Go dependencies", ["server/go/go.mod", "server/go/go.sum"], ["backend", "runtime"]],
  ["Helm only", ["deploy/helm/workpal/templates/deployment.yaml"], ["scripts"]],
  ["container entrypoint", ["docker/entrypoint.sh"], ["scripts"]],
  ["selfhost config", [".env.example"], ["backend", "scripts", "installer"]],
  ["selfhost compose", ["docker-compose.selfhost.yml"], ["backend", "scripts", "installer"]],
  ["local environment config", [".workpal/environments.toml"], ["backend", "scripts"]],
  ["plugin example", ["examples/plugins/hello-panel/workpal.plugin.json"], ["backend"]],
  ["shell installer", ["scripts/install.sh"], ["scripts", "installer"]],
  ["PowerShell installer", ["scripts/install.ps1.test.ps1"], ["installer"]],
  ["cleanup script", ["scripts/drop-database.sh"], ["scripts"]],
  ["check script regression tests", ["scripts/check.test.sh"], ["scripts"]],
  ["performance harness", ["scripts/perf-compare.test.sh"], ["scripts"]],
  ["attachment preview source", ["server/go/internal/handler/attachment_text_preview.json"], ["backend", "runtime", "scripts"]],
  ["attachment preview output", ["packages/views/editor/utils/text-preview-whitelist.generated.ts"], ["frontend", "quality", "scripts"]],
  ["reserved slug source", ["server/go/internal/handler/reserved_slugs.json"], ["backend", "runtime", "scripts"]],
  ["reserved slug output", ["packages/core/paths/reserved-slugs.ts"], ["frontend", "quality", "scripts"]],
  ["integration key gates", ["server/go/cmd/server/router.go"], ["backend", "runtime", "scripts"]],
  ["brand source", ["packages/ui/lib/workpal-brand.ts"], ["frontend", "quality"]],
  ["CLI brand copy", ["server/go/cmd/workpal/cmd_auth.go"], ["backend", "runtime", "quality"]],
  ["mobile brand copy", ["apps/mobile/components/brand/workpal-logo.tsx"], ["quality"]],
  ["README logo", ["docs/assets/logo-dark.svg"], ["quality"]],
  ["brand generator", ["scripts/brand/sync.mjs"], ["quality"]],
  ["PR evidence uploader", ["scripts/pr-shots"], ["quality"]],
  ["cross-module runtime contract", ["packages/core/runtimes/cli-version.ts"], ["frontend", "backend", "runtime", "quality"]],
  ["inbox type contract", ["packages/core/types/inbox.ts"], ["frontend", "backend", "quality"]],
  ["shared quick action body contract", ["server/go/internal/handler/testdata/quick_action_bodies.json"], ["frontend", "backend", "runtime"]],
  ["lockfile", ["pnpm-lock.yaml"], ["frontend", "quality", "docs"]],
  ["workspace catalog", ["pnpm-workspace.yaml"], ["frontend", "quality", "docs"]],
  ["workspace package patch", ["patches/example.patch"], ["frontend", "quality", "docs"]],
  ["mobile package patch", ["apps/mobile/patches/example.patch"], ["quality"]],
  ["radius policy", ["scripts/check-ui-radius-tokens.mjs"], ["quality"]],
  ["shared quality action", [".github/actions/frontend-quality/action.yml"], ["frontend", "quality"]],
  ["new bitmap", ["apps/web/public/hero.png"], ["frontend", "quality", "images"]],
  ["mixed docs and migration", ["apps/docs/content/guide.mdx", "server/go/migrations/999_example.up.sql"], ["quality", "docs", "backend", "sqlc"]],
  ["CI configuration", [".github/ci-paths.json"], Object.keys(filters)],
]) {
  test(`PR and main select only affected scopes: ${name}`, () => {
    for (const event of ["pull_request", "push"]) {
      const outputs = decideScopes(event, filterFiles(files));
      assert.equal(outputs.full, "false");
      assert.deepEqual(Object.keys(filters).filter((scope) => outputs[scope] === "true").sort(),
        [...selected].sort());
      assert.equal(outputs.quality_only, String(selected.includes("quality") && !selected.includes("frontend")));
    }
  });
}

test("scheduled and manual runs select every scope without a path-filter result", () => {
  for (const event of ["schedule", "workflow_dispatch"]) {
    const { quality_only, ...scopes } = decideScopes(event, {});
    assert.ok(Object.values(scopes).every((value) => value === "true"));
    assert.equal(quality_only, "false", "the full frontend build owns quality checks");
  }
});

test("missing, malformed and unsupported filter results fail closed", () => {
  for (const value of [undefined, "", "unknown", true]) {
    assert.throws(() => decideScopes("push", { ...filterFiles([]), backend: value }), /backend/);
  }
  assert.throws(() => decideScopes("unknown", filterFiles([])), /Unsupported/);
});

test("the CLI writes real Actions outputs and exits nonzero on a failed gate", (t) => {
  const dir = mkdtempSync(join(tmpdir(), "ci-scope-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const output = join(dir, "output");
  const script = fileURLToPath(new URL("./ci-scope.mjs", import.meta.url));
  const run = spawnSync(process.execPath, [script, "decide"], {
    env: { ...process.env, EVENT_NAME: "push", FILTER_RESULTS: JSON.stringify(filterFiles(["README.md"])), GITHUB_OUTPUT: output },
    encoding: "utf8",
  });
  assert.equal(run.status, 0, run.stderr);
  assert.match(readFileSync(output, "utf8"), /^backend=false$/m);
  const failed = {changes: {result: "success", outputs: decideScopes("workflow_dispatch", {})}, "backend-tests": {result: "failure"}};
  const gate = spawnSync(process.execPath, [script, "gate"], {
    env: { ...process.env, NEEDS_JSON: JSON.stringify(failed), JOB_SCOPES: JSON.stringify({"backend-tests": "backend"}) },
    encoding: "utf8",
  });
  assert.equal(gate.status, 1);
  assert.match(gate.stderr, /backend-tests/);
});
