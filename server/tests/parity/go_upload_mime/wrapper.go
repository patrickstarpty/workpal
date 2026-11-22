package handler
import("encoding/base64";"net/http";"path";"strings")
type ParityMIMEFixture struct{Data,Filename string}
func ParityMIME(f ParityMIMEFixture)any{data,e:=base64.StdEncoding.DecodeString(f.Data);if e!=nil{panic(e)};detected:=http.DetectContentType(data);upload:=detected;if ct,ok:=extContentTypes[strings.ToLower(path.Ext(f.Filename))];ok{upload=ct};return map[string]string{"detected":detected,"upload":upload}}
