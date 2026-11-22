package main
import("encoding/json";"os";"workpal.local/workpal/server/internal/handler")
func main(){
 var cases []struct{Raw string;Key string;Base string;Public string;Disabled bool;TTL float64}
 if err:=json.NewDecoder(os.Stdin).Decode(&cases);err!=nil{panic(err)}
 results:=make([]any,0,len(cases))
 for _,c:=range cases{results=append(results,handler.ParityAvatarURLs(c.Raw,c.Key,c.Base,c.Public,c.Disabled,c.TTL))}
 if err:=json.NewEncoder(os.Stdout).Encode(results);err!=nil{panic(err)}
}
