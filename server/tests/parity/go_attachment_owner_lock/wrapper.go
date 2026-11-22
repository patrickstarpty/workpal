package handler
import("context";"errors";"strings";"github.com/jackc/pgx/v5";"github.com/jackc/pgx/v5/pgconn";"github.com/jackc/pgx/v5/pgtype";"workpal.local/workpal/server/internal/util";db "workpal.local/workpal/server/pkg/db/generated")
type ParityOwnerFixture struct{Initial [2]string;Fresh [][2]string;Failure string;Actor bool}
type poDB struct{pgx.Tx;f ParityOwnerFixture;calls []any;attempt int}
func poID(s string)pgtype.UUID{v,_:=util.ParseUUID(s);return v}
const poA="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
const poW="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
func(q *poDB)record(kind string,args ...any)error{call:=[]any{kind};for _,a:=range args{if id,ok:=a.(pgtype.UUID);ok{call=append(call,util.UUIDToString(id))}else{call=append(call,a)}};q.calls=append(q.calls,call);switch q.f.Failure{case kind:return errors.New(kind+" failed");case kind+"-missing":return pgx.ErrNoRows;case kind+"-cancel":return context.Canceled};return nil}
func(q *poDB)Begin(context.Context)(pgx.Tx,error){q.attempt++;if e:=q.record("begin");e!=nil{return nil,e};return q,nil}
func(q *poDB)Exec(_ context.Context,sql string,args ...any)(pgconn.CommandTag,error){return pgconn.CommandTag{},q.record("execute",append([]any{sql},args...)...)}
func(q *poDB)Commit(context.Context)error{return q.record("commit")}
func(q *poDB)Rollback(context.Context)error{return q.record("rollback")}
func(q *poDB)QueryRow(_ context.Context,sql string,args ...any)pgx.Row{kind:="";switch{case strings.Contains(sql,"name: LockIssueForAttachmentWrite :one"):kind="issue";case strings.Contains(sql,"name: LockLiveComment :one"):kind="comment";case strings.Contains(sql,"name: GetAttachment :one"):kind="read";case strings.Contains(sql,"name: LockAttachmentRow :one"):kind="row";default:panic(sql)};return poRow{q,kind,q.record(kind,args...)}}
type poRow struct{q *poDB;kind string;err error}
func(r poRow)Scan(dest ...any)error{if r.err!=nil{return r.err};switch r.kind{case "issue":if len(dest)!=1{panic("issue columns")};case "comment":if len(dest)!=20{panic("comment columns")};default:if len(dest)!=17{panic("attachment columns")};i:=r.q.attempt-1;if i>=len(r.q.f.Fresh){i=len(r.q.f.Fresh)-1};fresh:=r.q.f.Fresh[i];*dest[0].(*pgtype.UUID)=poID(poA);*dest[1].(*pgtype.UUID)=poID(poW);*dest[2].(*pgtype.UUID)=poID(fresh[0]);*dest[3].(*pgtype.UUID)=poID(fresh[1])};return nil}
func ParityOwner(f ParityOwnerFixture)any{q:=&poDB{f:f,calls:[]any{}};h:=&Handler{Queries:db.New(q),TxStarter:q};ctx:=context.Background();att:=db.Attachment{ID:poID(poA),WorkspaceID:poID(poW),IssueID:poID(f.Initial[0]),CommentID:poID(f.Initial[1])};err:=h.withAttachmentOwnerLock(ctx,att,func(*db.Queries)error{return q.record("write")});message:="";if err!=nil{message=err.Error()};return map[string]any{"calls":q.calls,"error":message}}
