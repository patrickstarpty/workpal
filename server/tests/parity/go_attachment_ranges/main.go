package main
import("encoding/json";"os";"workpal.local/workpal/server/internal/handler")
func main(){var fixtures []handler.ParityRangeFixture;if e:=json.NewDecoder(os.Stdin).Decode(&fixtures);e!=nil{panic(e)};out:=[]any{};for _,f:=range fixtures{out=append(out,handler.ParityRange(f))};json.NewEncoder(os.Stdout).Encode(out)}
