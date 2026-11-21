package agent

import (
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func TestMuseAppTaskPromptRunsCLIWithTaskContext(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("POSIX shell execution")
	}
	cliPath := filepath.Join(t.TempDir(), "task cli's binary")
	script := "#!/bin/sh\nprintf '%s\\n' \"$WORKPAL_DAEMON_PORT\" \"$WORKPAL_TASK_ID\" \"$WORKPAL_AGENT_NAME\" \"$WORKPAL_TASK_CONFIG_ROOT\" \"$WORKPAL_SERVER_URL\" \"$WORKPAL_WORKSPACE_ID\" \"$WORKPAL_TOKEN\" \"$*\"\n"
	if err := os.WriteFile(cliPath, []byte(script), 0700); err != nil {
		t.Fatal(err)
	}
	env := map[string]string{
		"WORKPAL_CLI_PATH": cliPath, "WORKPAL_DAEMON_PORT": "12345",
		"WORKPAL_TASK_ID": "task-current", "WORKPAL_AGENT_NAME": "Muse's agent $(exit 99); literal",
		"WORKPAL_TASK_CONFIG_ROOT": filepath.Join(t.TempDir(), "task's config"),
		"WORKPAL_MUSEAPP_ENDPOINT": "http://untrusted.invalid", "WORKPAL_MUSEAPP_TOKEN": "private-receptionist-token",
		"WORKPAL_TOKEN": "private-config-token", "OTHER_SECRET": "private-custom-secret",
	}
	opts := ExecOptions{TaskToken: "private-task-token", WorkpalServerURL: "http://127.0.0.1:8080", WorkpalWorkspaceID: "ws-current"}
	prompt := museappTaskPrompt("check out the repository", env, opts, "linux")
	for _, secret := range []string{opts.TaskToken, env["WORKPAL_TOKEN"], env["WORKPAL_MUSEAPP_TOKEN"], env["OTHER_SECRET"], env["WORKPAL_MUSEAPP_ENDPOINT"]} {
		if strings.Contains(prompt, secret) {
			t.Fatal("credential or unapproved config leaked into task prompt")
		}
	}
	_, rest, ok := strings.Cut(prompt, "```\n")
	if !ok {
		t.Fatal("missing CLI prefix")
	}
	prefix, _, ok := strings.Cut(rest, "\n```")
	if !ok {
		t.Fatal("unterminated CLI prefix")
	}
	cmd := exec.Command("sh", "-c", prefix+" repo checkout https://example.invalid/repo.git")
	cmd.Env = []string{"PATH=/usr/bin:/bin", "WORKPAL_TOKEN=mat_current_task"}
	output, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("task CLI: %v: %s", err, output)
	}
	want := strings.Join([]string{env["WORKPAL_DAEMON_PORT"], env["WORKPAL_TASK_ID"], env["WORKPAL_AGENT_NAME"], env["WORKPAL_TASK_CONFIG_ROOT"], opts.WorkpalServerURL, opts.WorkpalWorkspaceID, "mat_current_task", "repo checkout https://example.invalid/repo.git", ""}, "\n")
	if string(output) != want {
		t.Fatalf("task CLI environment = %q, want %q", output, want)
	}
}

func TestMuseAppTaskPromptPowerShellContext(t *testing.T) {
	prompt := museappTaskPrompt("task", map[string]string{"WORKPAL_CLI_PATH": `C:\User's Files\workpal.exe`, "WORKPAL_DAEMON_PORT": "19514"}, ExecOptions{}, "windows")
	if !strings.Contains(prompt, `$env:WORKPAL_DAEMON_PORT = '19514'`) || !strings.Contains(prompt, `& 'C:\User''s Files\workpal.exe' @args }`) {
		t.Fatalf("missing quoted PowerShell context: %s", prompt)
	}
}
