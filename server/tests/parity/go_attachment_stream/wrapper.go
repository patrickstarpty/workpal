package handler
import("encoding/base64";"errors";"io";"net/http";"net/http/httptest";db "workpal.local/workpal/server/pkg/db/generated")
type ParityStreamFixture struct{Header string;Size int64;Data string;FailAt int;WriteFail bool}
type parityStreamReader struct{data []byte;position,failAt int}
func(r *parityStreamReader)Read(p []byte)(int,error){if r.failAt>=0&&r.position>=r.failAt{return 0,errors.New("fixture read failure")};if r.position>=len(r.data){return 0,io.EOF};n:=len(p);if n>2{n=2};if n>len(r.data)-r.position{n=len(r.data)-r.position};copy(p,r.data[r.position:r.position+n]);r.position+=n;return n,nil}
type parityStreamWriter struct{http.ResponseWriter;fail bool;writes int}
func(w *parityStreamWriter)Write(p []byte)(int,error){w.writes++;if w.fail{return 0,errors.New("fixture write failure")};return w.ResponseWriter.Write(p)}
func ParityStream(f ParityStreamFixture)any{
 r:=httptest.NewRequest("GET","http://internal/download",nil);r.Header.Set("Range",f.Header)
 w:=httptest.NewRecorder();w.Header().Set("Content-Type","application/octet-stream")
 reader:=&parityStreamReader{data:[]byte(f.Data),failAt:f.FailAt}
 writer:=&parityStreamWriter{ResponseWriter:w,fail:f.WriteFail};h:=&Handler{};h.serveProxyRange(writer,r,db.Attachment{SizeBytes:f.Size},reader)
 result:=w.Result();headers:=map[string]string{};for _,key:=range []string{"Accept-Ranges","Content-Range","Content-Length","Content-Type"}{headers[key]=result.Header.Get(key)}
 return map[string]any{"status":result.StatusCode,"headers":headers,"body":base64.StdEncoding.EncodeToString(w.Body.Bytes()),"read":reader.position,"writes":writer.writes}
}
