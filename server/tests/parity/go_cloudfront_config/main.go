package main
import("encoding/json";"os";"workpal.local/workpal/server/internal/auth")
func main(){os.Setenv("AWS_EC2_METADATA_DISABLED","true");var f []map[string]string;if e:=json.NewDecoder(os.Stdin).Decode(&f);e!=nil{panic(e)};out:=[]any{};for _,v:=range f{out=append(out,auth.ParityCFConfig(v))};json.NewEncoder(os.Stdout).Encode(out)}
