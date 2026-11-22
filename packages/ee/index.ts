import { registerProjectFoldersExtension } from "@workpal/views/extensions";
import { projectFoldersExtension } from "./project-folders/components";

/**
 * Turns on the commercial features (packages/ee) in an app. Call once at
 * startup, before the first render. Files in this package are covered by
 * ./LICENSE, not the Workpal License.
 */
export function registerEE(): void {
  registerProjectFoldersExtension(projectFoldersExtension);
}
