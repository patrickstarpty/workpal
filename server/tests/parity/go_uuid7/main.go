package main
import("encoding/json";"os";"github.com/google/uuid")
func main(){var fs []uuid.ParityV7Fixture;if e:=json.NewDecoder(os.Stdin).Decode(&fs);e!=nil{panic(e)};out:=[]any{};for _,f:=range fs{out=append(out,uuid.ParityV7(f))};json.NewEncoder(os.Stdout).Encode(out)}
