package handler
import "encoding/base64"
func ParityCSP(values []string)any{normalized:=[]any{};for _,v:=range values{s,ok:=normalizeFrameAncestorSource(v);if ok{normalized=append(normalized,base64.StdEncoding.EncodeToString([]byte(s)))}else{normalized=append(normalized,nil)}};return map[string]any{"sources":normalized,"csp":base64.StdEncoding.EncodeToString([]byte(attachmentPreviewCSPHeader(values)))}}
