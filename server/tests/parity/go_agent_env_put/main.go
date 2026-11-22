package main
import (
 "context"
 "encoding/json"
 "net/http/httptest"
 "os"
 "strings"
 "workpal.local/workpal/server/internal/events"
 "github.com/go-chi/chi/v5"
 "github.com/jackc/pgx/v5/pgxpool"
 "workpal.local/workpal/server/internal/handler"
 "workpal.local/workpal/server/internal/middleware"
 db "workpal.local/workpal/server/pkg/db/generated"
)
func main(){
 var input struct{Seeds []string; Cases []struct{Path string;Query string;User string;Headers map[string]string;SQL string;Body string}}
 if err:=json.NewDecoder(os.Stdin).Decode(&input);err!=nil{panic(err)}
 pool,err:=pgxpool.New(context.Background(),os.Getenv("DATABASE_URL"));if err!=nil{panic(err)};defer pool.Close()
 for _,sql:=range input.Seeds{if _,err:=pool.Exec(context.Background(),sql);err!=nil{panic(err)}}
 queries:=db.New(pool);bus:=events.New();emitted:=make([]any,0)
 bus.SubscribeAll(func(e events.Event){emitted=append(emitted,map[string]any{"type":e.Type,"workspaceID":e.WorkspaceID,"actorType":e.ActorType,"actorID":e.ActorID,"payload":e.Payload})})
 h:=handler.Handler{Queries:queries,TxStarter:pool,Bus:bus}
 router:=chi.NewRouter();router.Use(middleware.RequireWorkspaceMember(queries));router.Put("/api/agents/{id}/env",h.UpdateAgentEnv)
 results:=make([]any,0,len(input.Cases))
 for _,c:=range input.Cases{
  if c.SQL!="" {if _,err:=pool.Exec(context.Background(),c.SQL);err!=nil{panic(err)}}
  req:=httptest.NewRequest("PUT",c.Path,strings.NewReader(c.Body));req.URL.RawQuery=c.Query
  req.Header.Set("X-User-ID",c.User)
  for k,v:=range c.Headers{req.Header.Set(k,v)}
  w:=httptest.NewRecorder();router.ServeHTTP(w,req)
  var audits string
  err=pool.QueryRow(context.Background(),`SELECT COALESCE(json_agg(x),'[]')::text FROM
    (SELECT workspace_id,issue_id,actor_type,actor_id,action,details FROM activity_log ORDER BY created_at,id) x`).Scan(&audits)
  if err!=nil{panic(err)}
  var saved string
  if err:=pool.QueryRow(context.Background(),`SELECT custom_env::text FROM agent LIMIT 1`).Scan(&saved);err!=nil{panic(err)}
  snapshot,_:=json.Marshal(emitted)
  results=append(results,map[string]any{"status":w.Code,"body":w.Body.String(),"audits":json.RawMessage(audits),"events":json.RawMessage(snapshot),"saved":json.RawMessage(saved)})
 }
 if err:=json.NewEncoder(os.Stdout).Encode(results);err!=nil{panic(err)}
}
