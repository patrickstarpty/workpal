package middleware
import "net/http/httptest"
type ParityTokenFixture struct{Authorization []string;Cookies []string}
func ParityTokenSource(f ParityTokenFixture)any{
 r:=httptest.NewRequest("GET","http://internal/api/me",nil)
 for _,value:=range f.Authorization{r.Header.Add("Authorization",value)}
 for _,value:=range f.Cookies{r.Header.Add("Cookie",value)}
 token,cookie:=extractToken(r)
 return map[string]any{"token":token,"cookie":cookie}
}
