package main
import("encoding/json";"os";"workpal.local/workpal/server/internal/auth")
func main(){key,e:=os.ReadFile("/fixtures/cloudfront-test-key.pem");if e!=nil{panic(e)};var f []auth.ParityCFFixture;if e:=json.NewDecoder(os.Stdin).Decode(&f);e!=nil{panic(e)};out:=[]any{};for _,v:=range f{out=append(out,auth.ParityCF(key,v))};json.NewEncoder(os.Stdout).Encode(out)}
