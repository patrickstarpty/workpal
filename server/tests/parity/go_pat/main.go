// Isolated PAT handler oracle. Authentication is supplied as a fixture;
// this harness does not claim middleware or full-server equivalence.
package main
import (
 "context"
 "encoding/json"
 "net/http/httptest"
 "os"
 "strings"
 "time"
 "github.com/go-chi/chi/v5"
 "github.com/jackc/pgx/v5/pgxpool"
 "workpal.local/workpal/server/internal/handler"
 db "workpal.local/workpal/server/pkg/db/generated"
)
const owner="11111111-1111-4111-8111-111111111111"
func main(){
 ctx:=context.Background()
 pool,err:=pgxpool.New(ctx,os.Getenv("DATABASE_URL"));if err!=nil{panic(err)};defer pool.Close()
 schema,err:=os.ReadFile("/reference/server/go/migrations/011_personal_access_tokens.up.sql");if err!=nil{panic(err)}
 _,err=pool.Exec(ctx,`CREATE TABLE "user" (id uuid PRIMARY KEY); INSERT INTO "user" VALUES ('`+owner+`');`);if err!=nil{panic(err)}
 _,err=pool.Exec(ctx,string(schema));if err!=nil{panic(err)}
 h:=&handler.Handler{Queries:db.New(pool)}
 r:=chi.NewRouter();r.Use(handler.RequireHumanActor)
 r.Get("/api/tokens",h.ListPersonalAccessTokens);r.Post("/api/tokens",h.CreatePersonalAccessToken)
 r.Post("/api/tokens/current/renew",h.RenewCurrentPersonalAccessToken);r.Delete("/api/tokens/{id}",h.RevokePersonalAccessToken)
 type Case struct{Method string `json:"method"`;Path string `json:"path"`;Body string `json:"body"`;Actor string `json:"actor"`;Authorization string `json:"authorization"`}
 var payload struct{ Cases []Case `json:"cases"`; Seeds []struct{ID string `json:"id"`; Name string `json:"name"`; Hash string `json:"token_hash"`; Prefix string `json:"token_prefix"`; CreatedAt time.Time `json:"created_at"`; ExpiresAt *time.Time `json:"expires_at"`} `json:"seeds"` }
 if err=json.NewDecoder(os.Stdin).Decode(&payload);err!=nil{panic(err)}
 for _,seed:=range payload.Seeds {
  _,err=pool.Exec(ctx,"INSERT INTO personal_access_token(id,user_id,name,token_hash,token_prefix,created_at,expires_at) VALUES($1,$2,$3,$4,$5,$6,$7)",seed.ID,owner,seed.Name,seed.Hash,seed.Prefix,seed.CreatedAt,seed.ExpiresAt);if err!=nil{panic(err)}
 }
 cases:=payload.Cases
 observations:=make([]any,0,len(cases))
 for _,c:=range cases{
  req:=httptest.NewRequest(c.Method,c.Path,strings.NewReader(c.Body));req.Header.Set("X-User-ID",owner)
  req.Header.Set("X-Actor-Source",c.Actor);req.Header.Set("Authorization",c.Authorization)
  w:=httptest.NewRecorder();r.ServeHTTP(w,req)
  var body any
  if w.Body.Len()>0{if err=json.Unmarshal(w.Body.Bytes(),&body);err!=nil{panic(err)}}
  var stateBytes []byte
  if err=pool.QueryRow(ctx,`SELECT COALESCE(jsonb_agg(jsonb_build_object('id',id,'user_id',user_id,'name',name,'token_hash',token_hash,'token_prefix',token_prefix,'expires_at',extract(epoch from expires_at),'last_used_at',extract(epoch from last_used_at),'revoked',revoked,'created_at',extract(epoch from created_at)) ORDER BY id),'[]'::jsonb) FROM personal_access_token`).Scan(&stateBytes);err!=nil{panic(err)}
  var state any;if err=json.Unmarshal(stateBytes,&state);err!=nil{panic(err)}
  observations=append(observations,map[string]any{"status":w.Code,"headers":w.Header(),"body":body,"wire_body":w.Body.String(),"state":map[string]any{"tokens":state},"events":nil,"external_calls":nil})
 }
 if err=json.NewEncoder(os.Stdout).Encode(observations);err!=nil{panic(err)}
}
