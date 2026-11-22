# Keyboard-accessible ticket relationship picker
Revision 1. Prepared by Codex; review requested. Implementation is not implied.

## Entry and search
An explicitly labelled Add relationship button opens the picker and moves focus to its search input. The dialog names the source ticket and relationship type. Search results are scoped by the server to the active workspace and current member's access. Never show a private title first and rely on navigation failure to enforce authorization.

## Keyboard contract
Tab reaches search, relationship-type selection, results and Cancel without entering the background page. Arrow keys move among selectable results when using a listbox pattern; Enter selects the active result once. Escape closes without applying a pending selection and returns focus to Add relationship. A result's accessible name includes identifier and title. Loading and no-results states are announced once, without changing the selected relationship type or discarding search text.

## Creation and removal
Prevent self-reference and duplicate pairs. Disable submission while it is in flight; present the server error without closing the picker. On success expose a navigable ticket identifier and relationship type in the source ticket. Removal is a separately labelled button available by keyboard, never only on hover. After removal place focus on the next relation or Add relationship when the list becomes empty.

## Boundaries and layout
Validate target access again when saving. If permission changes while the picker is open, reject the mutation without returning target content. At 390px, search and relation type fit the dialog width, long titles wrap, and Cancel remains reachable. The target link retains a return route to the source ticket in the same workspace.

## Acceptance evidence
Capture keyboard-only add, Escape without mutation, empty search, failed save/retry, duplicate rejection, removal of the last relation, long titles and access revoked between search and save. Record actual focus targets and persisted relation IDs. No execution result or design acceptance is recorded in this version.
