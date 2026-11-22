package realtime
import("net/http";"net/netip";"net/url")
type ParityOriginFixture struct{Origin,Host,Remote,Forwarded string;Allowed,Proxies []string}
func ParityOrigin(f ParityOriginFixture)any{
 SetAllowedOrigins(f.Allowed);prefixes:=[]netip.Prefix{};for _,raw:=range f.Proxies{if p,e:=netip.ParsePrefix(raw);e==nil{prefixes=append(prefixes,p)}};SetTrustedProxies(prefixes)
 request:=&http.Request{Host:f.Host,RemoteAddr:f.Remote,Header:make(http.Header)};request.Header.Set("Origin",f.Origin);request.Header.Set("X-Forwarded-Host",f.Forwarded)
 host:="";u,e:=url.Parse(f.Origin);if e==nil{host=u.Host}
 return map[string]any{"allowed":checkOrigin(request),"trusted":isTrustedProxy(f.Remote),"host":host,"valid_url":e==nil}
}
