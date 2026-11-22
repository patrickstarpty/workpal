package main
import("encoding/json";"os";"workpal.local/workpal/server/internal/realtime")
func main(){var fixtures []struct{Frame []byte;Values map[string]any;Nanos int64};if e:=json.NewDecoder(os.Stdin).Decode(&fixtures);e!=nil{panic(e)};out:=[]any{};for _,f:=range fixtures{out=append(out,realtime.ParityEnvelope(f.Frame,f.Values,f.Nanos))};json.NewEncoder(os.Stdout).Encode(out)}
