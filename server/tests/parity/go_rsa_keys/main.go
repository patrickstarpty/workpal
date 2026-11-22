package main
import("encoding/json";"os";"workpal.local/workpal/server/internal/auth")
func main(){var f []string;if e:=json.NewDecoder(os.Stdin).Decode(&f);e!=nil{panic(e)};out:=[]any{};for _,v:=range f{out=append(out,auth.ParityRSAKey(v))};json.NewEncoder(os.Stdout).Encode(out)}
