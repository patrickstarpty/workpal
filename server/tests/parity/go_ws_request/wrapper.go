package realtime
import("context";"encoding/base64";"errors";"net/http/httptest")
type ParityWSRequestFixture struct{Query string;Cookies []string}
func ParityWSRequest(f ParityWSRequestFixture)any{
 SetAllowedOrigins([]string{});SetTrustedProxies(nil)
 r:=httptest.NewRequest("GET","http://internal/ws",nil);r.URL.RawQuery=f.Query
 r.Header.Set("Origin","https://forbidden.example");r.Header.Set("Upgrade","websocket");r.Header.Set("Connection","Upgrade");r.Header.Set("Sec-WebSocket-Version","13");r.Header.Set("Sec-WebSocket-Key","dGhlIHNhbXBsZSBub25jZQ==")
 for _,cookie:=range f.Cookies{r.Header.Add("Cookie",cookie)}
 value:="";cookie,e:=r.Cookie("workpal_auth");if e==nil{value=cookie.Value}
 slugs:=[]string{};resolver:=func(ctx context.Context,slug string)(string,error){slugs=append(slugs,slug);if slug=="good"{return "workspace",nil};return "",errors.New("not found")}
 recorder:=httptest.NewRecorder();HandleWebSocket(nil,nil,nil,resolver,recorder,r);response:=recorder.Result()
 headers:=map[string]string{};for _,key:=range []string{"Content-Type","X-Content-Type-Options","Sec-WebSocket-Version"}{headers[key]=response.Header.Get(key)}
 return map[string]any{"workspace":base64.StdEncoding.EncodeToString([]byte(r.URL.Query().Get("workspace_id"))),"cookie":value,"has_cookie":e==nil,"slugs":slugs,"status":response.StatusCode,"headers":headers,"body":base64.StdEncoding.EncodeToString(recorder.Body.Bytes())}
}
