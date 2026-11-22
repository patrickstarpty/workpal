package handler
import("context";"errors";"net/http/httptest";"strings";"github.com/go-chi/chi/v5";"github.com/jackc/pgx/v5";"github.com/jackc/pgx/v5/pgconn";"github.com/jackc/pgx/v5/pgtype";"workpal.local/workpal/server/internal/middleware";"workpal.local/workpal/server/internal/util";db "workpal.local/workpal/server/pkg/db/generated")
type ParityAttachmentLoaderFixture struct{Mode,ID,Workspace,StoredWorkspace,User,Failure string;Bound,Hidden,Cancelled bool}
const palP="dddddddd-dddd-dddd-dddd-dddddddddddd"
func palUUID(s string)pgtype.UUID{v,_:=util.ParseUUID(s);return v}
type palDB struct{f ParityAttachmentLoaderFixture;calls []any}
func(q *palDB)record(kind string,args ...any)error{call:=[]any{kind};call=append(call,args...);q.calls=append(q.calls,call);if q.f.Failure==kind{return errors.New("query failed")};if q.f.Failure==kind+"-missing"{return pgx.ErrNoRows};if q.f.Failure==kind+"-cancel"{return context.Canceled};return nil}
func(q *palDB)Exec(context.Context,string,...any)(pgconn.CommandTag,error){panic("unexpected Exec")}
type palRow struct{kind string;f ParityAttachmentLoaderFixture;err error}
func(r palRow)Scan(dest ...any)error{
 if r.err!=nil{return r.err}
 switch r.kind{
 case "scoped","attachment":if len(dest)!=17{panic("attachment columns")};*dest[0].(*pgtype.UUID)=palUUID(r.f.ID);*dest[1].(*pgtype.UUID)=palUUID(r.f.StoredWorkspace);if r.f.Bound{*dest[2].(*pgtype.UUID)=palUUID(palP)}
 case "member":if len(dest)!=6{panic("member columns")};*dest[1].(*pgtype.UUID)=palUUID(r.f.StoredWorkspace);*dest[2].(*pgtype.UUID)=palUUID(r.f.User)
 case "project":if len(dest)!=1{panic("project columns")};*dest[0].(*pgtype.UUID)=palUUID(palP)
 default:panic(r.kind)
 };return nil
}
func(q *palDB)QueryRow(_ context.Context,sql string,args ...any)pgx.Row{
 kind:="";switch{case strings.Contains(sql,"name: GetAttachment :one"):kind="scoped";case strings.Contains(sql,"name: GetAttachmentByIDOnly"):kind="attachment";case strings.Contains(sql,"name: GetMemberByUserAndWorkspace"):kind="member";case strings.Contains(sql,"name: GetIssueProjectID"):kind="project";default:panic(sql)}
 values:=[]any{};for _,arg:=range args{values=append(values,util.UUIDToString(arg.(pgtype.UUID)))}
 if kind=="member"{values[0],values[1]=values[1],values[0]}
 return palRow{kind,q.f,q.record(kind,values...)}
}
type palRows struct{pgx.Rows;hidden,done bool}
func(r *palRows)Next()bool{if r.done||!r.hidden{return false};r.done=true;return true}
func(r *palRows)Close(){}
func(r *palRows)Err()error{return nil}
func(r *palRows)Scan(dest ...any)error{if len(dest)!=1{panic("hidden columns")};*dest[0].(*pgtype.UUID)=palUUID(palP);return nil}
func(q *palDB)Query(_ context.Context,sql string,args ...any)(pgx.Rows,error){if !strings.Contains(sql,"name: ListHiddenProjectIDsForUser"){panic(sql)};if e:=q.record("hidden",util.UUIDToString(args[0].(pgtype.UUID)));e!=nil{return nil,e};return &palRows{hidden:q.f.Hidden},nil}
func ParityAttachmentLoader(f ParityAttachmentLoaderFixture)any{
 q:=&palDB{f:f,calls:[]any{}};h:=&Handler{Queries:db.New(q)}
 r:=httptest.NewRequest("GET","http://internal/",nil);r.Header.Set("X-User-ID",f.User);r.Header.Set("X-Workspace-ID",f.Workspace)
 route:=chi.NewRouteContext();route.URLParams.Add("id",f.ID);ctx:=context.WithValue(r.Context(),chi.RouteCtxKey,route)
 ws:=f.Workspace;if f.Mode=="download"{ws=f.StoredWorkspace}
 ctx=middleware.SetMemberContext(ctx,ws,db.Member{WorkspaceID:palUUID(ws),UserID:palUUID(f.User)})
 if f.Cancelled{next,cancel:=context.WithCancel(ctx);cancel();ctx=next};r=r.WithContext(ctx)
 w:=httptest.NewRecorder();var att db.Attachment;var ok bool
 if f.Mode=="download"{att,ok=h.loadAttachmentForDownload(w,r)}else{att,ok=h.loadAttachmentForRequest(w,r)}
 id:="";if ok{id=util.UUIDToString(att.ID)}
 return map[string]any{"ok":ok,"id":id,"status":w.Code,"body":w.Body.String(),"calls":q.calls}
}
