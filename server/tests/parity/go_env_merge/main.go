package main
import("encoding/json";"os";"strings";"workpal.local/workpal/server/internal/handler")
func main(){
 var cases []struct{Existing map[string]string;Requested map[string]string;Body *string}
 if err:=json.NewDecoder(os.Stdin).Decode(&cases);err!=nil{panic(err)}
 results:=make([]any,0,len(cases))
 for _,c:=range cases {
  if c.Body!=nil {
   var req handler.UpdateAgentEnvRequest
   if err:=json.NewDecoder(strings.NewReader(*c.Body)).Decode(&req);err!=nil {
    results=append(results,map[string]any{"error":"invalid request body"})
   } else {
    if req.CustomEnv==nil {req.CustomEnv=map[string]string{}}
    results=append(results,map[string]any{"decoded":req.CustomEnv})
   }
  } else {results=append(results,handler.ParityEnvMerge(c.Existing,c.Requested))}
 }
 if err:=json.NewEncoder(os.Stdout).Encode(results);err!=nil{panic(err)}
}
