package handler
import("context";"errors";"net/http/httptest";"strings";"github.com/jackc/pgx/v5";"github.com/jackc/pgx/v5/pgconn";"github.com/jackc/pgx/v5/pgtype";"workpal.local/workpal/server/internal/middleware";"workpal.local/workpal/server/internal/projectaccess";"workpal.local/workpal/server/internal/util";db "workpal.local/workpal/server/pkg/db/generated")
type ParityAttachmentAccessFixture struct{Mode,Project,Failure string;Issue,Comment,Empty bool;IDs []string}
const paaW="00000000-0000-0000-0000-000000000001"
const paaP="00000000-0000-0000-0000-000000000002"
const paaI="00000000-0000-0000-0000-000000000003"
const paaC="00000000-0000-0000-0000-000000000004"
const paaU="00000000-0000-0000-0000-000000000005"
const paaA="00000000-0000-0000-0000-000000000006"
const paaB="00000000-0000-0000-0000-000000000007"
func paaUUID(s string)pgtype.UUID{if s==""{return pgtype.UUID{}};v,e:=util.ParseUUID(s);if e!=nil{panic(e)};return v}
func paaStrings(ids []pgtype.UUID)[]string{if ids==nil{return nil};out:=[]string{};for _,v:=range ids{out=append(out,util.UUIDToString(v))};return out}
type paaDB struct{f ParityAttachmentAccessFixture;calls []any}
func(q *paaDB)record(kind string,args ...any)error{call:=[]any{kind};call=append(call,args...);q.calls=append(q.calls,call);if q.f.Failure==kind{return errors.New("query failed")};if q.f.Failure==kind+"-missing"{return pgx.ErrNoRows};return nil}
func(q *paaDB)Exec(context.Context,string,...any)(pgconn.CommandTag,error){panic("unexpected Exec")}
func(q *paaDB)attachment(id string)db.Attachment{a:=db.Attachment{ID:paaUUID(id),WorkspaceID:paaUUID(paaW)};if id==paaA{if q.f.Issue{a.IssueID=paaUUID(paaI)};if q.f.Comment{a.CommentID=paaUUID(paaC)}};return a}
type paaRows struct{pgx.Rows;values []any;index int}
func(r *paaRows)Next()bool{if r.index>=len(r.values){return false};r.index++;return true}
func(r *paaRows)Close(){}
func(r *paaRows)Err()error{return nil}
func(r *paaRows)Scan(dest ...any)error{switch value:=r.values[r.index-1].(type){case pgtype.UUID:if len(dest)!=1{panic("hidden columns")};*dest[0].(*pgtype.UUID)=value;case db.Attachment:if len(dest)!=17{panic("attachment columns")};*dest[0].(*pgtype.UUID)=value.ID;*dest[1].(*pgtype.UUID)=value.WorkspaceID;*dest[2].(*pgtype.UUID)=value.IssueID;*dest[3].(*pgtype.UUID)=value.CommentID;default:panic("unexpected row")};return nil}
func(q *paaDB)Query(_ context.Context,sql string,args ...any)(pgx.Rows,error){values:=[]any{};if strings.Contains(sql,"name: ListHiddenProjectIDsForUser :many"){if e:=q.record("hidden",util.UUIDToString(args[0].(pgtype.UUID)),util.UUIDToString(args[1].(pgtype.UUID)));e!=nil{return nil,e};if !q.f.Empty{values=append(values,paaUUID(paaP))}}else if strings.Contains(sql,"name: ListAttachmentsByIDs :many"){ids:=paaStrings(args[0].([]pgtype.UUID));if e:=q.record("attachments",util.UUIDToString(args[1].(pgtype.UUID)),ids);e!=nil{return nil,e};for _,id:=range []string{paaA,paaB}{for _,candidate:=range ids{if id==candidate{values=append(values,q.attachment(id));break}}}}else{panic(sql)};return &paaRows{values:values},nil}
type paaRow struct{value pgtype.UUID;err error}
func(r paaRow)Scan(dest ...any)error{if r.err!=nil{return r.err};if len(dest)!=1{panic("project columns")};*dest[0].(*pgtype.UUID)=r.value;return nil}
func(q *paaDB)QueryRow(_ context.Context,sql string,args ...any)pgx.Row{kind:="";if strings.Contains(sql,"name: GetIssueProjectID :one"){kind="issue"}else if strings.Contains(sql,"name: GetCommentIssueProjectID :one"){kind="comment"}else{panic(sql)};err:=q.record(kind,util.UUIDToString(args[0].(pgtype.UUID)));return paaRow{paaUUID(q.f.Project),err}}
func ParityAttachmentAccess(f ParityAttachmentAccessFixture)any{q:=&paaDB{f:f,calls:[]any{}};h:=&Handler{Queries:db.New(q)};hidden:=false;failed:=false;var output []string;if f.Mode=="single"{set,err:=projectaccess.ForMember(context.Background(),h.Queries,paaUUID(paaW),paaUUID(paaU));if err==nil{hidden,err=h.attachmentInHiddenProject(context.Background(),set,q.attachment(paaA))};failed=err!=nil}else{var ids []pgtype.UUID;if f.IDs!=nil{ids=[]pgtype.UUID{}};for _,id:=range f.IDs{ids=append(ids,paaUUID(id))};r:=httptest.NewRequest("POST","http://internal",nil);r.Header.Set("X-User-ID",paaU);r=r.WithContext(middleware.SetMemberContext(r.Context(),paaW,db.Member{WorkspaceID:paaUUID(paaW),UserID:paaUUID(paaU)}));result,ok:=h.visibleAttachmentIDs(httptest.NewRecorder(),r,paaUUID(paaW),ids);output=paaStrings(result);failed=!ok};return map[string]any{"hidden":hidden,"error":failed,"ids":output,"calls":q.calls}}
