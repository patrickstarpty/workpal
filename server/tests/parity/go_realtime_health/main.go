package main
import("encoding/json";"encoding/base64";"net";"net/http/httptest";"os";"strings")
type Header struct{Name string;Value []byte}
type Fixture struct{Token,Host string;Headers []Header}
func main(){var fs []Fixture;if e:=json.NewDecoder(os.Stdin).Decode(&fs);e!=nil{panic(e)};out:=[]any{};for _,f:=range fs{req:=httptest.NewRequest("GET","http://testserver/health/realtime",nil);req.RemoteAddr=net.JoinHostPort(f.Host,"1234");for _,h:=range f.Headers{req.Header.Add(h.Name,string(h.Value))};w:=httptest.NewRecorder();realtimeMetricsHandler(f.Token)(w,req);headers:=map[string]string{};for _,name:=range []string{"Content-Type","Cache-Control","WWW-Authenticate","X-Content-Type-Options"}{if v:=w.Header().Get(name);v!=""{headers[strings.ToLower(name)]=v}};out=append(out,map[string]any{"status":w.Code,"headers":headers,"body":base64.StdEncoding.EncodeToString(w.Body.Bytes())})};json.NewEncoder(os.Stdout).Encode(out)}
