package handler
import("context";"errors";"net/http/httptest";"strings";"github.com/jackc/pgx/v5";"github.com/jackc/pgx/v5/pgconn";"github.com/jackc/pgx/v5/pgtype";"workpal.local/workpal/server/internal/util";db "workpal.local/workpal/server/pkg/db/generated")
type ParityChatAccessFixture struct{Mode,Actor,User,Workspace,Session,Creator,Owner,Permission,Role,Target,TargetID,Failure string}
const pcW="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
const pcS="cccccccc-cccc-cccc-cccc-cccccccccccc"
const pcA="dddddddd-dddd-dddd-dddd-dddddddddddd"
func pcUUID(s string)pgtype.UUID{v,_:=util.ParseUUID(s);return v}
type pcDB struct{f ParityChatAccessFixture;calls []any}
func(q *pcDB)record(kind string,args ...any)error{call:=[]any{kind};call=append(call,args...);q.calls=append(q.calls,call);switch q.f.Failure{case kind:return errors.New("query failed");case kind+"-missing":return pgx.ErrNoRows;case kind+"-cancel":return context.Canceled};return nil}
func(q *pcDB)Exec(context.Context,string,...any)(pgconn.CommandTag,error){panic("unexpected Exec")}
type pcRow struct{q *pcDB;kind string;err error}
func(r pcRow)Scan(dest ...any)error{if r.err!=nil{return r.err};f:=r.q.f;switch r.kind{case "session","public":if len(dest)!=17{panic("session columns")};*dest[0].(*pgtype.UUID)=pcUUID(pcS);*dest[1].(*pgtype.UUID)=pcUUID(pcW);*dest[2].(*pgtype.UUID)=pcUUID(pcA);*dest[3].(*pgtype.UUID)=pcUUID(f.Creator);case "agent":if len(dest)!=29{panic("agent columns")};*dest[0].(*pgtype.UUID)=pcUUID(pcA);*dest[1].(*pgtype.UUID)=pcUUID(pcW);*dest[9].(*pgtype.UUID)=pcUUID(f.Owner);*dest[23].(*string)=f.Permission;case "member":if len(dest)!=6{panic("member columns")};*dest[3].(*string)=f.Role;default:panic(r.kind)};return nil}
func(q *pcDB)QueryRow(_ context.Context,sql string,args ...any)pgx.Row{kind:="";switch{case strings.Contains(sql,"name: GetChatSessionInWorkspace :one"):kind="session";case strings.Contains(sql,"name: GetPublicChatSessionInWorkspace :one"):kind="public";case strings.Contains(sql,"name: GetAgent :one"):kind="agent";case strings.Contains(sql,"name: GetMemberByUserAndWorkspace :one"):kind="member";default:panic(sql)};values:=[]any{};for _,v:=range args{values=append(values,util.UUIDToString(v.(pgtype.UUID)))};if kind=="member"{values[0],values[1]=values[1],values[0]};return pcRow{q,kind,q.record(kind,values...)}}
type pcRows struct{pgx.Rows;f ParityChatAccessFixture;done bool}
func(r *pcRows)Next()bool{if r.done||r.f.Target==""{return false};r.done=true;return true}
func(r *pcRows)Close(){}
func(r *pcRows)Err()error{return nil}
func(r *pcRows)Scan(dest ...any)error{if len(dest)!=6{panic("target columns")};*dest[2].(*string)=r.f.Target;*dest[3].(*pgtype.UUID)=pcUUID(r.f.TargetID);return nil}
func(q *pcDB)Query(_ context.Context,sql string,args ...any)(pgx.Rows,error){if !strings.Contains(sql,"name: ListAgentInvocationTargets :many"){panic(sql)};if e:=q.record("targets",util.UUIDToString(args[0].(pgtype.UUID)));e!=nil{return nil,e};return &pcRows{f:q.f},nil}
func ParityChatAccess(f ParityChatAccessFixture)any{q:=&pcDB{f:f,calls:[]any{}};h:=&Handler{Queries:db.New(q)};r:=httptest.NewRequest("GET","http://internal",nil);r.Header.Set("X-User-ID",f.User);if f.Actor=="agent"{r.Header.Set("X-Actor-Source","task_token");r.Header.Set("X-Agent-ID",pcA)};w:=httptest.NewRecorder();var ok bool;id:="";if f.Mode=="access"{ok=h.canAccessPrivateAgent(r.Context(),db.Agent{ID:pcUUID(pcA),OwnerID:pcUUID(f.Owner),PermissionMode:f.Permission},f.Actor,f.User,f.Workspace)}else{var row db.ChatSession;if f.Mode=="public"{row,ok=h.gatePublicChatSessionForUser(w,r,f.User,f.Workspace,f.Session)}else{row,ok=h.gateChatSessionForUser(w,r,f.User,f.Workspace,f.Session)};if ok{id=util.UUIDToString(row.ID)}};return map[string]any{"ok":ok,"id":id,"status":w.Code,"body":w.Body.String(),"calls":q.calls}}
