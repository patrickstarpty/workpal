package main
import("encoding/base64";"encoding/json";"os";"workpal.local/workpal/server/internal/imagemetadata")
func main(){var fixtures []string;if e:=json.NewDecoder(os.Stdin).Decode(&fixtures);e!=nil{panic(e)};out:=[]any{};for _,f:=range fixtures{raw,e:=base64.StdEncoding.DecodeString(f);if e!=nil{panic(e)};size,ok:=imagemetadata.Dimensions(raw);if ok{out=append(out,[]int32{size.Width,size.Height})}else{out=append(out,nil)}};json.NewEncoder(os.Stdout).Encode(out)}
