package metrics

import "testing"

func TestRegistryExcludesDatabaseSampledMetrics(t *testing.T) {
	registry := NewRegistry(RegistryOptions{})
	families, err := registry.Gatherer.Gather()
	if err != nil {
		t.Fatalf("gather metrics: %v", err)
	}

	retired := map[string]struct{}{
		"workpal_agent_task_queued":                               {},
		"workpal_agent_task_running":                              {},
		"workpal_agent_task_stuck_total":                          {},
		"workpal_business_sampler_query_errors_total":             {},
		"workpal_business_sampler_query_seconds":                  {},
		"workpal_workspace_total":                                 {},
		"workpal_seat_capacity_outbox_pending":                    {},
		"workpal_seat_capacity_outbox_dead_lettered":              {},
		"workpal_seat_capacity_outbox_oldest_pending_age_seconds": {},
		"workpal_channel_media_pending_objects":                   {},
		"workpal_channel_media_tombstoned_objects":                {},
		"workpal_runtime_gc_blocked_observation_failed_total":     {},
		"workpal_runtime_gc_blocked_runtimes":                     {},
		"workpal_runtime_gc_backlog_runtimes":                     {},
	}
	for _, family := range families {
		if _, found := retired[family.GetName()]; found {
			t.Errorf("retired database-sampled metric %q is still registered", family.GetName())
		}
	}
}
