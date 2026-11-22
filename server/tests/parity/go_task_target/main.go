package main
import (
 "context"
 "errors"
 "strings"
 "encoding/json"
 "net/http"
 "net/http/httptest"
 "os"
 "github.com/jackc/pgx/v5"
 "github.com/jackc/pgx/v5/pgconn"
 "github.com/jackc/pgx/v5/pgtype"
 "workpal.local/workpal/server/internal/auth"
 "workpal.local/workpal/server/internal/util"
 "workpal.local/workpal/server/internal/middleware"
 db "workpal.local/workpal/server/pkg/db/generated"
)
const (
	ttTestToken   = "mat_test_9403_token"
	ttWorkspaceA  = "0a0a0a0a-0000-4000-8000-00000000000a"
	ttWorkspaceB  = "0b0b0b0b-0000-4000-8000-00000000000b"
	ttUserID      = "11111111-0000-4000-8000-000000000001"
	ttAgentID     = "22222222-0000-4000-8000-000000000002"
	ttTaskID      = "33333333-0000-4000-8000-000000000003"
	ttSlugA       = "ws-a"
	ttSlugB       = "ws-b"
	ttSlugDBError = "ws-db-error"
)

// fakeTaskTokenDB is a minimal db.DBTX that answers the two queries the
// task-token auth path issues: GetTaskTokenByHash and GetWorkspaceBySlug.
// Anything else fails the test, so an unexpected query on this path is
// caught rather than silently returning zero values.
type fakeTaskTokenDB struct {
	
}

func (f *fakeTaskTokenDB) Exec(context.Context, string, ...interface{}) (pgconn.CommandTag, error) {
	
	return pgconn.CommandTag{}, errors.New("unexpected Exec")
}

func (f *fakeTaskTokenDB) Query(context.Context, string, ...interface{}) (pgx.Rows, error) {
	
	return nil, errors.New("unexpected Query")
}

func (f *fakeTaskTokenDB) QueryRow(_ context.Context, sql string, args ...interface{}) pgx.Row {
	switch {
	case strings.Contains(sql, "name: GetTaskTokenByHash"):
		if len(args) != 1 || args[0] != auth.HashToken(ttTestToken) {
			return fakeRow{err: pgx.ErrNoRows}
		}
		return fakeRow{scan: func(dest ...any) {
			*dest[0].(*pgtype.UUID) = util.MustParseUUID("44444444-0000-4000-8000-000000000004")
			*dest[2].(*pgtype.UUID) = util.MustParseUUID(ttTaskID)
			*dest[3].(*pgtype.UUID) = util.MustParseUUID(ttAgentID)
			*dest[4].(*pgtype.UUID) = util.MustParseUUID(ttWorkspaceA)
			*dest[5].(*pgtype.UUID) = util.MustParseUUID(ttUserID)
		}}
	case strings.Contains(sql, "name: GetWorkspaceBySlug"):
		var id string
		switch args[0] {
		case ttSlugA:
			id = ttWorkspaceA
		case ttSlugB:
			id = ttWorkspaceB
		case ttSlugDBError:
			return fakeRow{err: errors.New("connection reset")}
		default:
			return fakeRow{err: pgx.ErrNoRows}
		}
		return fakeRow{scan: func(dest ...any) {
			*dest[0].(*pgtype.UUID) = util.MustParseUUID(id)
		}}
	}
	
	return fakeRow{err: errors.New("unexpected QueryRow")}
}

type fakeRow struct {
	err  error
	scan func(dest ...any)
}

func (r fakeRow) Scan(dest ...any) error {
	if r.err != nil {
		return r.err
	}
	r.scan(dest...)
	return nil
}


func main() {
 var cases []struct{Query string;Headers map[string][]string}
 if err:=json.NewDecoder(os.Stdin).Decode(&cases);err!=nil {panic(err)}
 observations:=make([]any,0,len(cases))
 next:=http.HandlerFunc(func(w http.ResponseWriter,r *http.Request){w.WriteHeader(204)})
 wrapped:=middleware.Auth(db.New(&fakeTaskTokenDB{}),nil,nil,nil)(next)
 for _,c:=range cases {
  req:=httptest.NewRequest("POST","/api/upload-file",nil)
  req.URL.RawQuery=c.Query
  req.Header.Set("Authorization","Bearer "+ttTestToken)
  for k,values:=range c.Headers { for _,v:=range values {req.Header.Add(k,v)} }
  w:=httptest.NewRecorder()
  wrapped.ServeHTTP(w,req)
  observations=append(observations,map[string]any{"status":w.Code,"body":w.Body.String()})
 }
 if err:=json.NewEncoder(os.Stdout).Encode(observations);err!=nil {panic(err)}
}
