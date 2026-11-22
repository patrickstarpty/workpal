package main
import("encoding/json";"os";"workpal.local/workpal/server/internal/realtime")
func main(){var fixtures []struct{IDs []string;Concurrent bool};if err:=json.NewDecoder(os.Stdin).Decode(&fixtures);err!=nil{panic(err)};out:=[]any{};for _,f:=range fixtures{out=append(out,realtime.ParitySeen(f.IDs,f.Concurrent))};json.NewEncoder(os.Stdout).Encode(out)}
