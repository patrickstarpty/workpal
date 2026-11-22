package handler
// ParityEnvMerge is compiled only in the disposable oracle copy.
func ParityEnvMerge(existing, requested map[string]string) any {
 merged,audit:=mergeAgentEnv(existing,requested)
 return map[string]any{"merged":merged,"audit":map[string]any{
  "added_keys":audit.added,"removed_keys":audit.removed,"changed_keys":audit.changed,"preserved_keys":audit.preserved,
 }}
}
