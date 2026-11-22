package main
import("encoding/json";"os";"workpal.local/workpal/server/internal/handler")
func main(){var fixtures []handler.ParityContentFixture;if e:=json.NewDecoder(os.Stdin).Decode(&fixtures);e!=nil{panic(e)};out:=[]any{};for _,f:=range fixtures{out=append(out,handler.ParityContent(f))};json.NewEncoder(os.Stdout).Encode(out)}
