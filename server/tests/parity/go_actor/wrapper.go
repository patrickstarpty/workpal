package handler
import("context";"errors";"net/http/httptest";"strings";"github.com/jackc/pgx/v5";"github.com/jackc/pgx/v5/pgconn";"github.com/jackc/pgx/v5/pgtype";"workpal.local/workpal/server/internal/util";db "workpal.local/workpal/server/pkg/db/generated")
type ParityActorFixture struct{Source,User,Workspace,Agent,Task,StoredWorkspace,StoredAgent,Failure string}
type parityActorDB struct{f ParityActorFixture;calls []any}
func(q *parityActorDB)Exec(context.Context,string,...any)(pgconn.CommandTag,error){panic("unexpected Exec")}
func(q *parityActorDB)Query(context.Context,string,...any)(pgx.Rows,error){panic("unexpected Query")}
type parityActorRow struct{q *parityActorDB;kind string}
func(q *parityActorDB)QueryRow(_ context.Context,sql string,args ...any)pgx.Row{kind:="";if strings.Contains(sql,"name: GetAgent :one"){kind="agent"}else if strings.Contains(sql,"name: GetAgentTask :one"){kind="task"}else{panic(sql)};q.calls=append(q.calls,[]string{kind,util.UUIDToString(args[0].(pgtype.UUID))});return parityActorRow{q,kind}}
func(r parityActorRow)Scan(dest ...any)error{f:=r.q.f;if f.Failure==r.kind{return errors.New("query failed")};if f.Failure==r.kind+"-missing"{return pgx.ErrNoRows};if f.Failure==r.kind+"-cancel"{return context.Canceled};raw:=f.StoredAgent;count:=60;if r.kind=="agent"{raw=f.StoredWorkspace;count=29};if len(dest)!=count{panic("columns drift")};var id pgtype.UUID;if raw!=""{var e error;id,e=util.ParseUUID(raw);if e!=nil{panic(e)}};*dest[1].(*pgtype.UUID)=id;return nil}
func ParityActor(f ParityActorFixture)any{q:=&parityActorDB{f:f,calls:[]any{}};h:=&Handler{Queries:db.New(q)};r:=httptest.NewRequest("GET","http://internal",nil);r.Header.Set("X-Actor-Source",f.Source);r.Header.Set("X-Agent-ID",f.Agent);r.Header.Set("X-Task-ID",f.Task);kind,id:=h.resolveActor(r,f.User,f.Workspace);return map[string]any{"actor":[]string{kind,id},"calls":q.calls}}
