package main
import("encoding/json";"os";"workpal.local/workpal/server/internal/realtime")
func main(){var fixtures []struct{Frame []byte;ID []byte};if e:=json.NewDecoder(os.Stdin).Decode(&fixtures);e!=nil{panic(e)};out:=[][]byte{};for _,f:=range fixtures{out=append(out,realtime.ParityInjectEventID(f.Frame,f.ID))};json.NewEncoder(os.Stdout).Encode(out)}
