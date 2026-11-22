package main
import("encoding/json";"encoding/base64";"os";"workpal.local/workpal/server/internal/storage")
type fixture struct{Mime,Filename string;Force bool}
func main(){var fixtures []fixture;if e:=json.NewDecoder(os.Stdin).Decode(&fixtures);e!=nil{panic(e)};out:=[]string{};for _,f:=range fixtures{name,e:=base64.StdEncoding.DecodeString(f.Filename);if e!=nil{panic(e)};value:=storage.ContentDisposition(f.Mime,string(name));if f.Force{value=storage.AttachmentContentDisposition(string(name))};out=append(out,value)};json.NewEncoder(os.Stdout).Encode(out)}
