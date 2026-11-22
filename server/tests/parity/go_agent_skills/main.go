package main
import (
 "context"
 "encoding/json"
 "net/http/httptest"
 "os"
 "github.com/go-chi/chi/v5"
 "github.com/jackc/pgx/v5/pgxpool"
 "workpal.local/workpal/server/internal/handler"
 "workpal.local/workpal/server/internal/middleware"
 db "workpal.local/workpal/server/pkg/db/generated"
)
func main(){
 var input struct{Seeds []string; Cases []struct{Path string;Query string;User string;Headers map[string]string;SQL string}}
 if err:=json.NewDecoder(os.Stdin).Decode(&input);err!=nil{panic(err)}
 pool,err:=pgxpool.New(context.Background(),os.Getenv("DATABASE_URL"));if err!=nil{panic(err)};defer pool.Close()
 for _,sql:=range input.Seeds{if _,err:=pool.Exec(context.Background(),sql);err!=nil{panic(err)}}
 queries:=db.New(pool);h:=handler.Handler{Queries:queries}
 router:=chi.NewRouter();router.Use(middleware.RequireWorkspaceMember(queries));router.Get("/api/agents/{id}/skills",h.ListAgentSkills)
 results:=make([]any,0,len(input.Cases))
 for _,c:=range input.Cases{
  if c.SQL!="" {if _,err:=pool.Exec(context.Background(),c.SQL);err!=nil{panic(err)}}
  req:=httptest.NewRequest("GET",c.Path,nil);req.URL.RawQuery=c.Query
  req.Header.Set("X-User-ID",c.User)
  for k,v:=range c.Headers{req.Header.Set(k,v)}
  w:=httptest.NewRecorder();router.ServeHTTP(w,req)
  var audits string
  err=pool.QueryRow(context.Background(),`SELECT COALESCE(json_agg(x),'[]')::text FROM
    (SELECT workspace_id,issue_id,actor_type,actor_id,action,details FROM activity_log ORDER BY created_at,id) x`).Scan(&audits)
  if err!=nil{panic(err)}
  results=append(results,map[string]any{"status":w.Code,"body":w.Body.String(),"audits":json.RawMessage(audits)})
 }
 if err:=json.NewEncoder(os.Stdout).Encode(results);err!=nil{panic(err)}
}
