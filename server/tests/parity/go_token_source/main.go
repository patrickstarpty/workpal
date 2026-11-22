package main
import("encoding/json";"os";"workpal.local/workpal/server/internal/middleware")
func main(){var fixtures []middleware.ParityTokenFixture;if e:=json.NewDecoder(os.Stdin).Decode(&fixtures);e!=nil{panic(e)};out:=[]any{};for _,f:=range fixtures{out=append(out,middleware.ParityTokenSource(f))};json.NewEncoder(os.Stdout).Encode(out)}
