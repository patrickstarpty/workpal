package main
import("encoding/json";"os";"workpal.local/workpal/server/internal/handler")
func main(){var fixtures []handler.ParityPreviewFixture;if e:=json.NewDecoder(os.Stdin).Decode(&fixtures);e!=nil{panic(e)};out:=[]bool{};for _,f:=range fixtures{out=append(out,handler.ParityPreview(f))};json.NewEncoder(os.Stdout).Encode(out)}
