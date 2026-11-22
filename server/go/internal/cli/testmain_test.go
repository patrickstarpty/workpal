
package cli

import (
	"fmt"
	"os"
	"testing"

	"workpal.local/workpal/server/internal/testutil"
)

// TestMain redirects both home environment variables to one scratch directory
// for the whole binary before any test runs. This package owns SaveCLIConfig,
// which resolves ~/.workpal through os.UserHomeDir — USERPROFILE on Windows,
// HOME elsewhere. Tests that only redirect HOME therefore split the fixture's
// write path from the code's read path on Windows: SaveCLIConfig writes test
// fixtures over a real default-profile config.json. Process-wide redirection
// isolates tests that forget their own redirect on every platform; per-test
// t.Setenv overrides still take precedence.
func TestMain(m *testing.M) {
	for _, key := range []string{
		"WORKPAL_AGENT_ID",
		"WORKPAL_TASK_ID",
		"WORKPAL_TOKEN",
		"WORKPAL_DAEMON_PORT",
		"WORKPAL_WORKSPACE_ID",
		"WORKPAL_SERVER_URL",
		"WORKPAL_TASK_CONFIG_ROOT",
	} {
		os.Unsetenv(key)
	}

	scratchHome, err := testutil.IsolateUserHome("workpal-cli-config-tests-home-")
	if err != nil {
		fmt.Fprintf(os.Stderr, "isolate internal/cli test home: %v\n", err)
		os.Exit(1)
	}

	code := m.Run()
	_ = os.RemoveAll(scratchHome)
	os.Exit(code)
}

var redirectTestHome = testutil.RedirectUserHome
