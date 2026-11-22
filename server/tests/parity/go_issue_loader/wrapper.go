package handler
import("context";"errors";"net/http/httptest";"strings";"github.com/go-chi/chi/v5";"github.com/jackc/pgx/v5";"github.com/jackc/pgx/v5/pgconn";"github.com/jackc/pgx/v5/pgtype";"workpal.local/workpal/server/internal/middleware";"workpal.local/workpal/server/internal/util";db "workpal.local/workpal/server/pkg/db/generated")
type ParityIssueLoaderFixture struct{ID,Workspace,User,Failure,Prefix,Name string;Bound,Hidden,Cancelled bool}
const pilP="dddddddd-dddd-dddd-dddd-dddddddddddd"
func pilUUID(s string)pgtype.UUID{v,_:=util.ParseUUID(s);return v}
type pilDB struct{f ParityIssueLoaderFixture;calls []any}
func(q *pilDB)record(kind string,args ...any)error{call:=[]any{kind};call=append(call,args...);q.calls=append(q.calls,call);if q.f.Failure==kind{return errors.New("query failed")};if q.f.Failure==kind+"-missing"{return pgx.ErrNoRows};if q.f.Failure==kind+"-cancel"{return context.Canceled};return nil}
func(q *pilDB)Exec(context.Context,string,...any)(pgconn.CommandTag,error){panic("unexpected Exec")}
type pilRow struct{kind string;f ParityIssueLoaderFixture;err error}
func(r pilRow)Scan(dest ...any)error{
 if r.err!=nil{return r.err}
 switch r.kind{
 case "workspace":if len(dest)!=13{panic("workspace columns")};*dest[0].(*pgtype.UUID)=pilUUID(r.f.Workspace);*dest[1].(*string)=r.f.Name;*dest[9].(*string)=r.f.Prefix
 case "issue","number":if len(dest)!=31{panic("issue columns")};*dest[0].(*pgtype.UUID)=pilUUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");*dest[1].(*pgtype.UUID)=pilUUID(r.f.Workspace);if r.f.Bound{*dest[18].(*pgtype.UUID)=pilUUID(pilP)}
 default:panic(r.kind)
 };return nil
}
func(q *pilDB)QueryRow(_ context.Context,sql string,args ...any)pgx.Row{
 kind:="";switch{case strings.Contains(sql,"name: GetWorkspace :one"):kind="workspace";case strings.Contains(sql,"name: GetIssueInWorkspace :one"):kind="issue";case strings.Contains(sql,"name: GetIssueByNumber :one"):kind="number";default:panic(sql)}
 values:=[]any{};for _,arg:=range args{if id,ok:=arg.(pgtype.UUID);ok{values=append(values,util.UUIDToString(id))}else{values=append(values,arg)}}
 return pilRow{kind,q.f,q.record(kind,values...)}
}
type pilRows struct{pgx.Rows;hidden,done bool}
func(r *pilRows)Next()bool{if r.done||!r.hidden{return false};r.done=true;return true}
func(r *pilRows)Close(){}
func(r *pilRows)Err()error{return nil}
func(r *pilRows)Scan(dest ...any)error{if len(dest)!=1{panic("hidden columns")};*dest[0].(*pgtype.UUID)=pilUUID(pilP);return nil}
func(q *pilDB)Query(_ context.Context,sql string,args ...any)(pgx.Rows,error){if !strings.Contains(sql,"name: ListHiddenProjectIDsForUser"){panic(sql)};if e:=q.record("hidden",util.UUIDToString(args[0].(pgtype.UUID)));e!=nil{return nil,e};return &pilRows{hidden:q.f.Hidden},nil}
func ParityIssueLoader(f ParityIssueLoaderFixture)any{
 q:=&pilDB{f:f,calls:[]any{}};h:=&Handler{Queries:db.New(q)}
 r:=httptest.NewRequest("GET","http://internal/",nil);r.Header.Set("X-User-ID",f.User);r.Header.Set("X-Workspace-ID",f.Workspace)
 route:=chi.NewRouteContext();route.URLParams.Add("id",f.ID);ctx:=context.WithValue(r.Context(),chi.RouteCtxKey,route)
 ws:=f.Workspace
 ctx=middleware.SetMemberContext(ctx,ws,db.Member{WorkspaceID:pilUUID(ws),UserID:pilUUID(f.User)})
 if f.Cancelled{next,cancel:=context.WithCancel(ctx);cancel();ctx=next};r=r.WithContext(ctx)
 w:=httptest.NewRecorder();var att db.Issue;var ok bool
 att,ok=h.loadIssueForUser(w,r,f.ID)
 id:="";if ok{id=util.UUIDToString(att.ID)}
 return map[string]any{"ok":ok,"id":id,"status":w.Code,"body":w.Body.String(),"calls":q.calls}
}
