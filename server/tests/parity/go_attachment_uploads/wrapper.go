package handler
import("bytes";"context";"crypto/sha256";"encoding/hex";"encoding/json";"errors";"net/http/httptest";"path";"strings";"github.com/jackc/pgx/v5";"github.com/jackc/pgx/v5/pgconn";"github.com/jackc/pgx/v5/pgtype";"workpal.local/workpal/server/internal/storage";"workpal.local/workpal/server/internal/events";"workpal.local/workpal/server/internal/util";db "workpal.local/workpal/server/pkg/db/generated")
type ParityUploadFixture struct{Body []byte;ContentType,User,Workspace,Query,Failure,Source,Agent,Task,TaskAgent,TaskSession,Session,Creator string;Storage,Cancelled,Stable,Revisions bool}
const puI="cccccccc-cccc-cccc-cccc-cccccccccccc"
const puC="dddddddd-dddd-dddd-dddd-dddddddddddd"
func puUUID(s string)pgtype.UUID{v,_:=util.ParseUUID(s);return v}
func puValue(v any)any{switch x:=v.(type){case pgtype.UUID:if !x.Valid{return nil};return util.UUIDToString(x);case []pgtype.UUID:out:=[]string{};for _,id:=range x{out=append(out,util.UUIDToString(id))};return out;case pgtype.Int4:if !x.Valid{return nil};return x.Int32;default:return v}}
type puDB struct{f ParityUploadFixture;calls []any;identity string;created []any}
func(q *puDB)record(kind string,args ...any)error{call:=[]any{kind};for _,v:=range args{call=append(call,puValue(v))};q.calls=append(q.calls,call);switch q.f.Failure{case kind:return errors.New(kind+" failed");case kind+"-missing":return pgx.ErrNoRows;case kind+"-cancel":return context.Canceled};return nil}
func(q *puDB)Exec(context.Context,string,...any)(pgconn.CommandTag,error){panic("unexpected DB Exec")}
type puRows struct{pgx.Rows}
func(r puRows)Next()bool{return false}
func(r puRows)Close(){}
func(r puRows)Err()error{return nil}
type puMany struct{pgx.Rows;q *puDB;kind string;done bool}
func(r *puMany)Next()bool{if r.done{return false};r.done=true;return true}
func(r *puMany)Close(){}
func(r *puMany)Err()error{return nil}
func(r *puMany)Scan(dest ...any)error{if r.kind=="attachments"{if len(dest)!=17{panic("attachment columns")};var i,c int64;return (puRow{q:r.q,kind:"create",args:r.q.created}).Scan(append(dest,&i,&c)...)};if len(dest)!=7{panic("reaction columns")};*dest[0].(*pgtype.UUID)=puUUID(puI);*dest[1].(*pgtype.UUID)=puUUID(puC);*dest[2].(*pgtype.UUID)=puUUID(r.q.f.Workspace);*dest[3].(*string)="member";*dest[4].(*pgtype.UUID)=puUUID(r.q.f.User);*dest[5].(*string)="ok";return nil}
func(q *puDB)Query(_ context.Context,sql string,args ...any)(pgx.Rows,error){kind:="";switch{case strings.Contains(sql,"name: ListPrivateProjectIDs :many"):return puRows{},q.record("private",args...);case strings.Contains(sql,"name: ListReactionsByCommentIDs :many"):kind="reactions";case strings.Contains(sql,"name: ListAttachmentsByCommentIDs :many"):kind="attachments";default:panic(sql)};if e:=q.record(kind,args...);e!=nil{return nil,e};return &puMany{q:q,kind:kind},nil}

type puRow struct{q *puDB;kind string;args []any;err error}
func(q *puDB)QueryRow(_ context.Context,sql string,args ...any)pgx.Row{kind:="";switch{case strings.Contains(sql,"name: GetChatSessionInWorkspace :one"):kind="session";case strings.Contains(sql,"name: GetPublicChatSessionInWorkspace :one"):kind="public_session";case strings.Contains(sql,"name: GetAgent :one"):kind="agent";case strings.Contains(sql,"name: GetAgentTask :one"):kind="source_task";case strings.Contains(sql,"name: GetAgentTaskInWorkspace :one"):kind="upload_task";case strings.Contains(sql,"name: GetMemberByUserAndWorkspace :one"):kind="member";case strings.Contains(sql,"name: GetIssueInWorkspace :one"):kind="issue";case strings.Contains(sql,"name: GetComment :one"):kind="comment";case strings.Contains(sql,"name: GetCommentInWorkspace :one"):kind="comment_event";case strings.Contains(sql,"name: LockLiveComment :one"):kind="lock";case strings.Contains(sql,"name: CreateAttachment :one"):kind="create";default:panic(sql)};if kind=="create"{q.created=args};values:=append([]any{},args...);if kind=="member"{values[0],values[1]=values[1],values[0]};return puRow{q,kind,args,q.record(kind,values...)}}
func(r puRow)Scan(dest ...any)error{if r.err!=nil{return r.err};switch r.kind{
case "session","public_session":if len(dest)!=17{panic("session columns")};*dest[0].(*pgtype.UUID)=puUUID(r.q.f.Session);*dest[1].(*pgtype.UUID)=puUUID(r.q.f.Workspace);*dest[2].(*pgtype.UUID)=puUUID(r.q.f.TaskAgent);*dest[3].(*pgtype.UUID)=puUUID(r.q.f.Creator);case "agent":if len(dest)!=29{panic("agent columns")};*dest[0].(*pgtype.UUID)=puUUID(r.q.f.TaskAgent);*dest[1].(*pgtype.UUID)=puUUID(r.q.f.Workspace);*dest[9].(*pgtype.UUID)=puUUID(r.q.f.User);case "source_task","upload_task":if len(dest)!=60{panic("task columns")};*dest[0].(*pgtype.UUID)=puUUID(r.q.f.Task);*dest[1].(*pgtype.UUID)=puUUID(r.q.f.TaskAgent);*dest[16].(*pgtype.UUID)=puUUID(r.q.f.TaskSession);case "member":if len(dest)!=6{panic("member columns")};*dest[3].(*string)="member"
case "issue":if len(dest)!=31{panic("issue columns")};*dest[0].(*pgtype.UUID)=puUUID(puI);*dest[1].(*pgtype.UUID)=puUUID(r.q.f.Workspace)
case "comment","lock","comment_event":if len(dest)!=20{panic("comment columns")};*dest[0].(*pgtype.UUID)=puUUID(puC);*dest[1].(*pgtype.UUID)=puUUID(puI);*dest[9].(*pgtype.UUID)=puUUID(r.q.f.Workspace);*dest[2].(*string)="member";*dest[3].(*pgtype.UUID)=puUUID(r.q.f.User);*dest[4].(*string)="body";*dest[5].(*string)="text";*dest[16].(*int64)=6
case "create":if len(dest)!=19{panic("attachment create columns")};a:=r.args;*dest[0].(*pgtype.UUID)=a[0].(pgtype.UUID);*dest[1].(*pgtype.UUID)=a[1].(pgtype.UUID);*dest[2].(*pgtype.UUID)=a[8].(pgtype.UUID);*dest[3].(*pgtype.UUID)=a[9].(pgtype.UUID);*dest[4].(*string)=a[2].(string);*dest[5].(*pgtype.UUID)=a[3].(pgtype.UUID);*dest[6].(*string)=a[4].(string);*dest[7].(*string)=a[5].(string);*dest[8].(*string)=a[6].(string);*dest[9].(*int64)=a[7].(int64);*dest[11].(*pgtype.UUID)=a[10].(pgtype.UUID);*dest[13].(*pgtype.UUID)=a[11].(pgtype.UUID);*dest[14].(*pgtype.UUID)=a[12].(pgtype.UUID);*dest[15].(*pgtype.Int4)=a[13].(pgtype.Int4);*dest[16].(*pgtype.Int4)=a[14].(pgtype.Int4);if r.q.f.Revisions{if a[8].(pgtype.UUID).Valid{*dest[17].(*int64)=5};if a[9].(pgtype.UUID).Valid{*dest[18].(*int64)=6}}
default:panic(r.kind)};return nil}
type puTx struct{pgx.Tx;q *puDB}
func(t puTx)QueryRow(ctx context.Context,sql string,args ...any)pgx.Row{return t.q.QueryRow(ctx,sql,args...)}
func(t puTx)Exec(_ context.Context,sql string,args ...any)(pgconn.CommandTag,error){values:=[]any{sql};values=append(values,args...);return pgconn.CommandTag{},t.q.record("execute",values...)}
func(t puTx)Commit(context.Context)error{return t.q.record("commit")}
func(t puTx)Rollback(context.Context)error{return t.q.record("rollback")}
type puStarter struct{q *puDB}
func(s puStarter)Begin(context.Context)(pgx.Tx,error){if e:=s.q.record("begin");e!=nil{return nil,e};return puTx{q:s.q},nil}
type puStorage struct{storage.Storage;q *puDB}
func(s puStorage)Upload(_ context.Context,key string,data []byte,media,name string)(string,error){s.q.identity=strings.TrimSuffix(path.Base(key),path.Ext(key));sum:=sha256.Sum256(data);if e:=s.q.record("upload",key,hex.EncodeToString(sum[:]),media,name);e!=nil{return "",e};return "https://storage/object",nil}
func(s puStorage)KeyFromURL(string)string{return "object"}
func(s puStorage)CdnDomain()string{return ""}
func(s puStorage)DeleteKeys(_ context.Context,keys []string){s.q.record("delete",keys)}
func ParityUpload(f ParityUploadFixture)any{q:=&puDB{f:f,calls:[]any{}};bus:=events.New();bus.SubscribeAll(func(e events.Event){q.record("publish",e.Type,e.WorkspaceID,e.ActorType,e.ActorID,e.Payload)});h:=&Handler{Queries:db.New(q),TxStarter:puStarter{q},Bus:bus};if f.Storage{h.Storage=puStorage{q:q}};r:=httptest.NewRequest("POST","http://internal/api/upload-file?"+f.Query,bytes.NewReader(f.Body));r.Header.Set("Content-Type",f.ContentType);r.Header.Set("X-Actor-Source",f.Source);r.Header.Set("X-Agent-ID",f.Agent);r.Header.Set("X-Task-ID",f.Task);r.Header.Set("X-User-ID",f.User);r.Header.Set("X-Workspace-ID",f.Workspace);if f.Stable{r.Header.Set("X-Client-Capabilities","stable_attachment_urls")};if f.Cancelled{ctx,cancel:=context.WithCancel(r.Context());cancel();r=r.WithContext(ctx)};w:=httptest.NewRecorder();h.UploadFile(w,r);var body any;if err:=json.Unmarshal(w.Body.Bytes(),&body);err!=nil&&w.Body.Len()>0{panic(err)};return map[string]any{"status":w.Code,"body":body,"calls":q.calls,"generated_id":q.identity}}
