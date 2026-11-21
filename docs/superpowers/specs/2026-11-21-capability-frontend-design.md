# Capability home frontend integration

The user approved the three-view concept in `outputs/workpal-capability-hub.html` and explicitly requested implementation in the frontend. This records that approved scope.

The three layers are login, capability home, and Workspace. After authentication, the entry route opens Overview at `/home`; sibling views use `/home/skills` and `/home/team`. `/home` is an existing reserved namespace, so permitted workspace names such as `landing` remain usable. Skill Hub and Agent Team are sibling routes. Enter Workspace opens the existing membership resolver; direct workspace links keep their existing behavior. A return link brings users from the workspace to capabilities. Existing workspace functions, backend behavior, SQLite records and review notes remain intact.

The UI uses native React views and Workpal components, typography, and appearance state. An embedded HTML document would isolate theme, navigation and accessibility state, so the approved concept is translated into React instead. The scoped chart CSS retains the arrow-free lifecycle, subtle glass surfaces and responsive squad matrix.

The catalog contains the existing 203 source-linked entries and 11 independent type categories. All stage and role references use catalog IDs. These are catalog capabilities and suggested squad compositions, not installed skills, deployed agents or measured execution results. No model execution or installation is added.

Only FWD and Default are selectable; FWD is the initial theme. One persistent appearance boundary covers login, capability pages, workspace selection and Workspace. Light, dark and system modes and persisted choices are shared across these layers. Retired theme selections fall back safely without deleting unrelated preferences or theme records.

Keyboard navigation, input composition/caret, detail focus/scroll and responsive layouts are part of the acceptance criteria. Run frontend interaction tests, `npm run check`, and Playwright against an isolated test backend without model calls.
