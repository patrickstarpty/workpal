// Actual Go Auth middleware, with no database or production dependencies.
package main
import (
 "encoding/json"
 "net/http"
 "net/http/httptest"
 "os"
 "workpal.local/workpal/server/internal/middleware"
)
func main(){
 var cases []struct{Method string `json:"method"`;Headers map[string]string `json:"headers"`}
 if err:=json.NewDecoder(os.Stdin).Decode(&cases);err!=nil{panic(err)}
 next:=http.HandlerFunc(func(w http.ResponseWriter,r *http.Request){w.Header().Set("X-Fixture-User",r.Header.Get("X-User-ID"));w.WriteHeader(204)})
 wrapped:=middleware.Auth(nil,nil,nil,nil)(next)
 observations:=make([]any,0,len(cases))
 for _,c:=range cases{
  req:=httptest.NewRequest(c.Method,"/fixture/identity",nil)
  for k,v:=range c.Headers{req.Header.Set(k,v)}
  w:=httptest.NewRecorder();wrapped.ServeHTTP(w,req)
  observations=append(observations,map[string]any{"status":w.Code,"body":w.Body.String(),"headers":w.Header(),"user_id":w.Header().Get("X-Fixture-User")})
 }
 if err:=json.NewEncoder(os.Stdout).Encode(observations);err!=nil{panic(err)}
}
