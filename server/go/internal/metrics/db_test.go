package metrics

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"
)

func TestDBCollectorExposesPoolStats(t *testing.T) {
	pool, err := pgxpool.New(context.Background(), "postgres://workpal:workpal@127.0.0.1:1/workpal?sslmode=disable&pool_max_conns=13")
	if err != nil {
		t.Fatalf("create pool: %v", err)
	}
	defer pool.Close()
	replicaPool, err := pgxpool.New(context.Background(), "postgres://workpal:workpal@127.0.0.1:2/workpal?sslmode=disable&pool_max_conns=7")
	if err != nil {
		t.Fatalf("create replica pool: %v", err)
	}
	defer replicaPool.Close()

	registry := NewRegistry(RegistryOptions{Pool: pool, ReplicaPool: replicaPool})
	rec := httptest.NewRecorder()
	NewHandler(registry.Gatherer).ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/metrics", nil))
	body := rec.Body.String()

	for _, want := range []string{
		"workpal_db_pool_acquired_conns",
		"workpal_db_pool_idle_conns",
		"workpal_db_pool_max_conns",
		"workpal_db_pool_acquire_duration_seconds_total",
	} {
		if !strings.Contains(body, want) {
			t.Fatalf("metrics body missing %q\n%s", want, body)
		}
	}
	for _, want := range []string{
		`workpal_db_pool_max_conns{role="primary"} 13`,
		`workpal_db_pool_max_conns{role="replica"} 7`,
	} {
		if !strings.Contains(body, want) {
			t.Fatalf("metrics body missing %q\n%s", want, body)
		}
	}
}

func TestDBRoutingMetricsExposeOnlyReadRoutes(t *testing.T) {
	registry := NewRegistry(RegistryOptions{})
	registry.DBRouting.RecordReadRoute("dashboard", "primary", "connection_failed")

	rec := httptest.NewRecorder()
	NewHandler(registry.Gatherer).ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/metrics", nil))
	body := rec.Body.String()
	if want := `workpal_db_read_routes_total{business="dashboard",reason="connection_failed",role="primary"} 1`; !strings.Contains(body, want) {
		t.Fatalf("metrics body missing %q\n%s", want, body)
	}
	for _, removed := range []string{
		"workpal_db_replica_configured",
		"workpal_db_replica_healthy",
		"workpal_db_replica_lag_bytes",
		"workpal_db_replica_replay_lag_seconds",
		"workpal_db_replica_probes_total",
		"workpal_db_replica_fallbacks_total",
	} {
		if strings.Contains(body, removed) {
			t.Fatalf("metrics body contains removed metric %q\n%s", removed, body)
		}
	}
}
