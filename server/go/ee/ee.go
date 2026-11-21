// Package ee links the commercial server features into the binary. Each
// subpackage registers itself with package extension from init.
//
// Files under server/ee are not covered by the Workpal License; see
// server/ee/LICENSE.
package ee

import (
	_ "workpal.local/workpal/server/ee/projectfolder"
)
