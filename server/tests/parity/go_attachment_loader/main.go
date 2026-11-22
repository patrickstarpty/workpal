package main
import("encoding/json";"os";"workpal.local/workpal/server/internal/handler")
func main(){var f []handler.ParityAttachmentLoaderFixture;if e:=json.NewDecoder(os.Stdin).Decode(&f);e!=nil{panic(e)};out:=[]any{};for _,v:=range f{out=append(out,handler.ParityAttachmentLoader(v))};json.NewEncoder(os.Stdout).Encode(out)}
