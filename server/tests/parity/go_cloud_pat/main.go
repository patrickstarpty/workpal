package main

import (
 "context"
 "encoding/json"
 "errors"
 "io"
 "net/http"
 "net/http/httptest"
 "os"
 "workpal.local/workpal/server/internal/auth"
)
type fixture struct {
 Body string `json:"body"`
 Status int `json:"status"`
 Token string `json:"token"`
 Owner string `json:"owner"`
}
func main() {
 var cases []fixture
 if err:=json.NewDecoder(os.Stdin).Decode(&cases);err!=nil { panic(err) }
 observations:=make([]any,0,len(cases))
 for _,c:=range cases {
  calls:=make([]any,0); owners:=make([]string,0)
  server:=httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter,r *http.Request){
   raw,_:=io.ReadAll(r.Body)
   calls=append(calls,map[string]any{"method":r.Method,"path":r.URL.Path,"body":string(raw),"content_type":r.Header.Get("Content-Type"),"accept":r.Header.Get("Accept")})
   w.WriteHeader(c.Status);w.Write([]byte(c.Body))
  }))
  v:=auth.NewCloudPATVerifier(auth.CloudPATVerifierConfig{FleetBaseURL:server.URL})
  id,err:=v.Verify(context.Background(),c.Token,func(_ context.Context,owner string)(bool,error){
   owners=append(owners,owner)
   if c.Owner=="error" {return false,errors.New("offline")}
   return c.Owner=="exists",nil
  })
  kind:="ok"
  if err!=nil {kind="unavailable";if errors.Is(err,auth.ErrCloudPATInvalid) {kind="invalid"}}
  observations=append(observations,map[string]any{"kind":kind,"identity":id,"calls":calls,"owners":owners})
  server.Close()
 }
 if err:=json.NewEncoder(os.Stdout).Encode(observations);err!=nil {panic(err)}
}
