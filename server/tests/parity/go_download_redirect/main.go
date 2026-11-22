package main
import("encoding/json";"net/http";"net/http/httptest";"os")
type fixture struct{Target,Path,Method,ContentType string}
func main(){var fixtures []fixture;if e:=json.NewDecoder(os.Stdin).Decode(&fixtures);e!=nil{panic(e)};out:=[]any{};for _,f:=range fixtures{r:=httptest.NewRequest(f.Method,"http://internal"+f.Path,nil);w:=httptest.NewRecorder();if f.ContentType!=""{w.Header().Set("Content-Type",f.ContentType)};http.Redirect(w,r,f.Target,302);out=append(out,map[string]any{"status":w.Code,"body":w.Body.String(),"location":w.Header().Get("Location"),"content_type":w.Header().Get("Content-Type")})};json.NewEncoder(os.Stdout).Encode(out)}
