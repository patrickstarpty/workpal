package main
import("bytes";"encoding/hex";"encoding/json";"os";"github.com/oklog/ulid/v2")
type Fixture struct{MS uint64;Entropy string}
func main(){var fs []Fixture;if err:=json.NewDecoder(os.Stdin).Decode(&fs);err!=nil{panic(err)};out:=[]string{};for _,f:=range fs{b,e:=hex.DecodeString(f.Entropy);if e!=nil{panic(e)};id,e:=ulid.New(f.MS,bytes.NewReader(b));if e!=nil{out=append(out,e.Error())}else{out=append(out,id.String())}};json.NewEncoder(os.Stdout).Encode(out)}
