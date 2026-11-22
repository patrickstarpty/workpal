package handler
import("context";"encoding/json";"time";"errors";"net/http/httptest";"strings";"github.com/go-chi/chi/v5";"github.com/jackc/pgx/v5";"github.com/jackc/pgx/v5/pgconn";"github.com/jackc/pgx/v5/pgtype";"workpal.local/workpal/server/internal/middleware";"workpal.local/workpal/server/internal/util";db "workpal.local/workpal/server/pkg/db/generated")
type ParityListingFixture struct{ID,Workspace,User,Failure,Prefix,Name string;Bound,Hidden,Cancelled,Stable bool;Comments []string;Origins []plOrigin}
type plOrigin struct{ID,AuthorType,AuthorID string;Time bool}
const pilP="dddddddd-dddd-dddd-dddd-dddddddddddd"
func pilUUID(s string)pgtype.UUID{v,_:=util.ParseUUID(s);return v}
type pilDB struct{f ParityListingFixture;calls []any}
func(q *pilDB)record(kind string,args ...any)error{call:=[]any{kind};call=append(call,args...);q.calls=append(q.calls,call);if q.f.Failure==kind{return errors.New("query failed")};if q.f.Failure==kind+"-missing"{return pgx.ErrNoRows};if q.f.Failure==kind+"-cancel"{return context.Canceled};return nil}
func(q *pilDB)Exec(context.Context,string,...any)(pgconn.CommandTag,error){panic("unexpected Exec")}
type pilRow struct{kind string;f ParityListingFixture;err error}
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
func(q *pilDB)queryHidden(_ context.Context,sql string,args ...any)(pgx.Rows,error){if !strings.Contains(sql,"name: ListHiddenProjectIDsForUser"){panic(sql)};if e:=q.record("hidden",util.UUIDToString(args[0].(pgtype.UUID)));e!=nil{return nil,e};return &pilRows{hidden:q.f.Hidden},nil}
type plRows struct{pgx.Rows;q *pilDB;kind string;index int}
func(r *plRows)Next()bool{r.index++;if r.kind=="attachments"{return r.index<len(r.q.f.Comments)};return r.index<len(r.q.f.Origins)}
func(r *plRows)Close(){}
func(r *plRows)Err()error{return nil}
func(r *plRows)Scan(dest ...any)error{if r.kind=="attachments"{if len(dest)!=17{panic("attachment columns")};*dest[0].(*pgtype.UUID)=pilUUID(pilP);*dest[1].(*pgtype.UUID)=pilUUID(r.q.f.Workspace);*dest[2].(*pgtype.UUID)=pilUUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");*dest[3].(*pgtype.UUID)=pilUUID(r.q.f.Comments[r.index]);*dest[4].(*string)="member";*dest[6].(*string)="file.txt";*dest[7].(*string)="https://storage/object";*dest[8].(*string)="text/plain";*dest[9].(*int64)=3;return nil};if len(dest)!=4{panic("origin columns")};o:=r.q.f.Origins[r.index];*dest[0].(*pgtype.UUID)=pilUUID(o.ID);*dest[1].(*string)=o.AuthorType;*dest[2].(*pgtype.UUID)=pilUUID(o.AuthorID);if o.Time{*dest[3].(*pgtype.Timestamptz)=pgtype.Timestamptz{Time:time.Date(2026,11,22,12,0,0,0,time.UTC),Valid:true}};return nil}
func(q *pilDB)Query(ctx context.Context,sql string,args ...any)(pgx.Rows,error){kind:="";switch{case strings.Contains(sql,"name: ListAttachmentsByIssue :many"):kind="attachments";case strings.Contains(sql,"name: ListCommentOriginsForIssue :many"):kind="origins";default:return q.queryHidden(ctx,sql,args...)};values:=[]any{};for _,arg:=range args{switch v:=arg.(type){case pgtype.UUID:values=append(values,util.UUIDToString(v));case []pgtype.UUID:ids:=[]string{};for _,id:=range v{ids=append(ids,util.UUIDToString(id))};values=append(values,ids);default:panic("unexpected argument")}};if err:=q.record(kind,values...);err!=nil{return nil,err};return &plRows{q:q,kind:kind,index:-1},nil}
func ParityListing(f ParityListingFixture)any{
 q:=&pilDB{f:f,calls:[]any{}};h:=&Handler{Queries:db.New(q)}
 r:=httptest.NewRequest("GET","http://internal/",nil);r.Header.Set("X-User-ID",f.User);r.Header.Set("X-Workspace-ID",f.Workspace)
 if f.Stable{r.Header.Set("X-Client-Capabilities","stable_attachment_urls")};route:=chi.NewRouteContext();route.URLParams.Add("id",f.ID);ctx:=context.WithValue(r.Context(),chi.RouteCtxKey,route)
 ws:=f.Workspace
 ctx=middleware.SetMemberContext(ctx,ws,db.Member{WorkspaceID:pilUUID(ws),UserID:pilUUID(f.User)})
 if f.Cancelled{next,cancel:=context.WithCancel(ctx);cancel();ctx=next};r=r.WithContext(ctx)
 w:=httptest.NewRecorder();h.ListAttachments(w,r);var body any;if w.Body.Len()>0{if err:=json.Unmarshal(w.Body.Bytes(),&body);err!=nil{panic(err)}}
 return map[string]any{"status":w.Code,"body":body,"raw_body":w.Body.String(),"calls":q.calls}
}
