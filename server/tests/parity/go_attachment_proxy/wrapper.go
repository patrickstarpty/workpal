package handler
import("bytes";"context";"errors";"io";"net/http/httptest";"strings";"workpal.local/workpal/server/internal/storage";db "workpal.local/workpal/server/pkg/db/generated")
type ParityProxyFixture struct{Body,Method,Range,ContentType,Filename,Failure string;Size int64;Seekable,Force,Cancelled bool;Ancestors []string}
type ppReader struct{r *bytes.Reader;closed *bool;failure string}
func(r *ppReader)Read(p []byte)(int,error){if r.failure=="read"{return 0,errors.New("read failed")};return r.r.Read(p)}
func(r *ppReader)Close()error{*r.closed=true;return nil}
type ppSeeker struct{*ppReader}
func(r *ppSeeker)Seek(offset int64,whence int)(int64,error){if r.failure=="seek"{return 0,errors.New("seek failed")};return r.r.Seek(offset,whence)}
type ppStorage struct{storage.Storage;f ParityProxyFixture;closed bool}
func(s *ppStorage)GetReader(context.Context,string)(io.ReadCloser,error){if s.f.Failure=="open"{return nil,errors.New("open failed")};if s.f.Failure=="open-cancel"{return nil,context.Canceled};r:=&ppReader{bytes.NewReader([]byte(s.f.Body)),&s.closed,s.f.Failure};if s.f.Seekable{return &ppSeeker{r},nil};return r,nil}
func ParityProxy(f ParityProxyFixture)any{
 s:=&ppStorage{f:f};h:=&Handler{Storage:s,cfg:Config{AttachmentFrameAncestors:f.Ancestors}}
 r:=httptest.NewRequest(f.Method,"http://internal/attachment",nil);r.Header.Set("Range",f.Range)
 if f.Cancelled{ctx,cancel:=context.WithCancel(r.Context());cancel();r=r.WithContext(ctx)}
 w:=httptest.NewRecorder();h.proxyAttachmentDownload(w,r,db.Attachment{ContentType:f.ContentType,Filename:f.Filename,SizeBytes:f.Size},"key",f.Force)
 headers:=map[string]string{};body:=w.Body.String();for k,v:=range w.Result().Header{if strings.ToLower(k)!="content-length"{headers[strings.ToLower(k)]=v[0]}}
 if value:=headers["content-type"];strings.HasPrefix(value,"multipart/byteranges; boundary="){boundary:=strings.TrimPrefix(value,"multipart/byteranges; boundary=");body=strings.ReplaceAll(body,boundary,strings.Repeat("x",60));headers["content-type"]="multipart/byteranges; boundary="+strings.Repeat("x",60)}
 return map[string]any{"status":w.Code,"headers":headers,"body":body,"closed":s.closed}
}
