package agent

import "strings"

// The receptionist does not spawn a daemon child, so cfg.Env is not inherited.
// Put the non-secret daemon task context in the prompt the existing worker
// already executes. A per-command prefix also works across independent shells.
// Credentials stay in task_token, never in model-visible command prefixes.
func museappTaskPrompt(prompt string, env map[string]string, opts ExecOptions, goos string) string {
	cliPath := env["WORKPAL_CLI_PATH"]
	if cliPath == "" {
		return prompt // Standalone Backend callers need not use the Workpal CLI.
	}
	keys := []string{
		"WORKPAL_CLI_PATH", "WORKPAL_DAEMON_PORT", "WORKPAL_TASK_ID",
		"WORKPAL_AGENT_ID", "WORKPAL_AGENT_NAME", "WORKPAL_TASK_SLOT",
		"WORKPAL_TASK_CONFIG_ROOT", "WORKPAL_TASK_WORKSPACES_ROOT",
		"WORKPAL_AUTOPILOT_ID", "WORKPAL_AUTOPILOT_RUN_ID",
		"WORKPAL_QUICK_CREATE_TASK_ID", "WORKPAL_QUICK_CREATE_ATTACHMENT_IDS",
		"WORKPAL_QUICK_CREATE_DEFAULT_ASSIGNEE_TYPE", "WORKPAL_QUICK_CREATE_DEFAULT_ASSIGNEE_ID",
	}
	values := make(map[string]string, len(keys)+2)
	for _, key := range keys {
		if value := env[key]; value != "" {
			values[key] = value
		}
	}
	keys = append(keys, "WORKPAL_SERVER_URL", "WORKPAL_WORKSPACE_ID")
	values["WORKPAL_SERVER_URL"] = opts.WorkpalServerURL
	values["WORKPAL_WORKSPACE_ID"] = opts.WorkpalWorkspaceID
	var command strings.Builder
	if goos == "windows" {
		command.WriteString("& { ")
		for _, key := range keys {
			if value := values[key]; value != "" {
				command.WriteString("$env:" + key + " = " + powerShellQuote(value) + "; ")
			}
		}
		command.WriteString("& " + powerShellQuote(cliPath) + " @args }")
	} else {
		command.WriteString("env")
		for _, key := range keys {
			if value := values[key]; value != "" {
				command.WriteString(" " + shellQuote(key+"="+value))
			}
		}
		command.WriteString(" " + shellQuote(cliPath))
	}
	return "[Workpal task CLI environment]\n" +
		"For every Workpal CLI command in the task or AGENTS.md, including commands shown as workpal or $WORKPAL_CLI_PATH, use the following prefix and append the original command arguments. Use it on every invocation, even in a new shell. The daemon and worker share these paths.\n\n" +
		"```\n" + command.String() + "\n```\n\n" +
		"In each shell invocation, set WORKPAL_TOKEN from this task's request.json task_token as instructed by the receptionist worker setup; do not rely on an earlier shell's exports. Never substitute an owner credential or an installed CLI for this task's credential and CLI.\n\n" + prompt
}
