package auth
import("time")
type ParityCFFixture struct{URL,KeyPairID,Domain,CookieDomain,Disposition string;Expiry int64}
func ParityCF(pem []byte,f ParityCFFixture)any{key,err:=parseRSAPrivateKey(pem);if err!=nil{panic(err)};s:=&CloudFrontSigner{privateKey:key,keyPairID:f.KeyPairID,domain:f.Domain,cookieDomain:f.CookieDomain};expiry:=time.Unix(f.Expiry,0);cookies:=[]any{};for _,c:=range s.SignedCookies(expiry){cookies=append(cookies,map[string]any{"name":c.Name,"value":c.Value,"domain":c.Domain,"path":c.Path,"expires":c.Expires.Unix(),"secure":c.Secure,"http_only":c.HttpOnly,"same_site":"none"})};return map[string]any{"download":s.SignedURLWithContentDisposition(f.URL,f.Disposition,expiry),"url":s.SignedURL(f.URL,expiry),"cookies":cookies}}
