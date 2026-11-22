package main
import("encoding/json";"os";"workpal.local/workpal/server/internal/handler")
func main(){var fs []handler.ParityDownloadsFixture;if e:=json.NewDecoder(os.Stdin).Decode(&fs);e!=nil{panic(e)};out:=[]any{};for _,f:=range fs{out=append(out,handler.ParityDownloads(f))};json.NewEncoder(os.Stdout).Encode(out)}
