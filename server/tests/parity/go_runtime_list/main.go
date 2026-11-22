package main
import (
 "context"
 "encoding/json"
 "net/http"
 "net/http/httptest"
 "os"
 "github.com/jackc/pgx/v5/pgxpool"
 "workpal.local/workpal/server/internal/handler"
 "workpal.local/workpal/server/internal/middleware"
 db "workpal.local/workpal/server/pkg/db/generated"
)
func main(){
 var input struct{Seeds []string; Cases []struct{Query string;User string;Headers map[string]string}}
 if err:=json.NewDecoder(os.Stdin).Decode(&input);err!=nil{panic(err)}
 pool,err:=pgxpool.New(context.Background(),os.Getenv("DATABASE_URL"));if err!=nil{panic(err)};defer pool.Close()
 for _,sql:=range input.Seeds{if _,err:=pool.Exec(context.Background(),sql);err!=nil{panic(err)}}
 queries:=db.New(pool);h:=handler.Handler{Queries:queries}
 wrapped:=middleware.RequireWorkspaceMember(queries)(http.HandlerFunc(h.ListAgentRuntimes))
 results:=make([]any,0,len(input.Cases))
 for _,c:=range input.Cases{
  req:=httptest.NewRequest("GET","/api/runtimes",nil);req.URL.RawQuery=c.Query
  req.Header.Set("X-User-ID",c.User)
  for k,v:=range c.Headers{req.Header.Set(k,v)}
  w:=httptest.NewRecorder();wrapped.ServeHTTP(w,req)
  results=append(results,map[string]any{"status":w.Code,"body":w.Body.String(),"headers":w.Header()})
 }
 if err:=json.NewEncoder(os.Stdout).Encode(results);err!=nil{panic(err)}
}
