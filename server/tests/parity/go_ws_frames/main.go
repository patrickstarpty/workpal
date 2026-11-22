package main
import("encoding/json";"os";"workpal.local/workpal/server/internal/realtime")
func main(){var fixtures []struct{Raw []byte;Mode string};if e:=json.NewDecoder(os.Stdin).Decode(&fixtures);e!=nil{panic(e)};out:=[]any{};for _,f:=range fixtures{out=append(out,realtime.ParityHandleFrame(f.Raw,f.Mode))};json.NewEncoder(os.Stdout).Encode(out)}
