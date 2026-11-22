package auth
import("encoding/base64")
func ParityRSAKey(raw string)any{pem,err:=base64.StdEncoding.DecodeString(raw);if err!=nil{panic(err)};key,err:=parseRSAPrivateKey(pem);if err!=nil{return nil};return map[string]any{"n":key.N.Text(16),"e":key.E,"bits":key.N.BitLen()}}
