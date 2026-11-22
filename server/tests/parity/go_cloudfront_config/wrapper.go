package auth
import("os";"time")
func ParityCFConfig(f map[string]string)any{for _,key:=range []string{"CLOUDFRONT_KEY_PAIR_ID","CLOUDFRONT_DOMAIN","COOKIE_DOMAIN","CLOUDFRONT_PRIVATE_KEY","CLOUDFRONT_PRIVATE_KEY_SECRET"}{os.Unsetenv(key);if value,ok:=f[key];ok{os.Setenv(key,value)}};s:=NewCloudFrontSignerFromEnv();if s==nil{return nil};return s.SignedURL("https://cdn.test/a",time.Unix(1700000000,0))}
