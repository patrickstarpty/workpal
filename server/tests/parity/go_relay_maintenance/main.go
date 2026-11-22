package main
import("encoding/json";"os";"workpal.local/workpal/server/internal/realtime")
func main(){var fixtures []realtime.ParityMaintenanceFixture;if e:=json.NewDecoder(os.Stdin).Decode(&fixtures);e!=nil{panic(e)};out:=[]any{};for _,f:=range fixtures{out=append(out,realtime.ParityMaintenance(f))};json.NewEncoder(os.Stdout).Encode(out)}
