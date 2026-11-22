package main
import("context";"encoding/json";"errors";"os";"github.com/jackc/pgx/v5";"github.com/jackc/pgx/v5/pgtype";"workpal.local/workpal/server/internal/util";db "workpal.local/workpal/server/pkg/db/generated")
type fixture struct{Scope string;User string;Workspace string;ID string;Issue bool;Orphan bool;Failure string;Missing bool}
type queries struct{f fixture;calls []string}
func uid(i byte)pgtype.UUID{v:=pgtype.UUID{Valid:true};v.Bytes[15]=i;return v}
func(q *queries)read(name string)error{q.calls=append(q.calls,name);if q.f.Failure==name{if q.f.Missing{return pgx.ErrNoRows};return errors.New("database down")};return nil}
func(q *queries)GetAgentTask(context.Context,pgtype.UUID)(db.AgentTaskQueue,error){if e:=q.read("task");e!=nil{return db.AgentTaskQueue{},e};t:=db.AgentTaskQueue{};if !q.f.Orphan{t.ChatSessionID=uid(3)};if q.f.Issue{t.IssueID=uid(5)};return t,nil}
func(q *queries)GetIssue(context.Context,pgtype.UUID)(db.Issue,error){e:=q.read("issue");return db.Issue{WorkspaceID:uid(2)},e}
func(q *queries)GetChatSession(context.Context,pgtype.UUID)(db.ChatSession,error){e:=q.read("chat");return db.ChatSession{WorkspaceID:uid(2),CreatorID:uid(1)},e}
func main(){_ = util.UUIDToString;var fixtures []fixture;if e:=json.NewDecoder(os.Stdin).Decode(&fixtures);e!=nil{panic(e)};out:=[]any{};for _,f:=range fixtures{q:=&queries{f:f,calls:[]string{}};ok,e:=newScopeAuthorizer(q).AuthorizeScope(context.Background(),f.User,f.Workspace,f.Scope,f.ID);message:="";if e!=nil{message=e.Error()};out=append(out,map[string]any{"allowed":ok,"error":message,"calls":q.calls})};json.NewEncoder(os.Stdout).Encode(out)}
