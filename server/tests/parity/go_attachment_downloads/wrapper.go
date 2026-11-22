package handler
import("bytes";"context";"errors";"io";"net/http/httptest";"strings";"time";"github.com/go-chi/chi/v5";"github.com/jackc/pgx/v5";"workpal.local/workpal/server/internal/storage";db "workpal.local/workpal/server/pkg/db/generated")
type ParityDownloadsFixture struct{Mode,Store,Failure,URL,Filename,ContentType,Method string;TTL int64}
type pdRow struct{pgx.Row;f ParityDownloadsFixture}
func(r pdRow)Scan(dest ...any)error{if e:=r.Row.Scan(dest...);e!=nil{return e};if len(dest)==17{*dest[6].(*string)=r.f.Filename;*dest[7].(*string)=r.f.URL;*dest[8].(*string)=r.f.ContentType;*dest[9].(*int64)=3};return nil}
type pdDB struct{*palDB;f ParityDownloadsFixture}
func(q *pdDB)QueryRow(ctx context.Context,sql string,args ...any)pgx.Row{return pdRow{q.palDB.QueryRow(ctx,sql,args...),q.f}}
type pdStorage struct{storage.Storage;calls *[]any;closed *bool}
func(s pdStorage)KeyFromURL(raw string)string{*s.calls=append(*s.calls,[]any{"key",raw});return "key"}
type pdReader struct{*bytes.Reader;closed *bool}
func(r pdReader)Close()error{*r.closed=true;return nil}
func(s pdStorage)GetReader(context.Context,string)(io.ReadCloser,error){*s.calls=append(*s.calls,[]any{"read","key"});return pdReader{bytes.NewReader([]byte("abc")),s.closed},nil}
type pdPresigner struct{pdStorage;failure string}
func(s pdPresigner)PresignGetWithContentDisposition(ctx context.Context,key string,ttl time.Duration,disposition string)(string,error){*s.calls=append(*s.calls,[]any{"presign",key,int64(ttl),disposition});if s.failure=="presign"{return "",errors.New("sign failed")};if s.failure=="presign-cancel"{return "",context.Canceled};return "https://cdn.example/signed?a=1&b=2",nil}
func ParityDownloads(f ParityDownloadsFixture)any{
 base:=ParityAttachmentLoaderFixture{Mode:"download",ID:"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",StoredWorkspace:"bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",User:"cccccccc-cccc-cccc-cccc-cccccccccccc",Failure:f.Failure}
 q:=&pdDB{&palDB{f:base,calls:[]any{}},f};calls:=[]any{};closed:=false;s:=pdStorage{calls:&calls,closed:&closed}
 h:=&Handler{Queries:db.New(q),cfg:Config{AttachmentDownloadMode:f.Mode,AttachmentDownloadURLTTL:time.Duration(f.TTL),AttachmentFrameAncestors:[]string{"https://app.example/path"}}}
 if f.Store=="plain"{h.Storage=s}else if f.Store=="presigner"{h.Storage=pdPresigner{s,f.Failure}}
 r:=httptest.NewRequest(f.Method,"http://internal/api/attachments/id/download",nil);r.Header.Set("X-User-ID",base.User)
 route:=chi.NewRouteContext();route.URLParams.Add("id",base.ID);r=r.WithContext(context.WithValue(r.Context(),chi.RouteCtxKey,route))
 w:=httptest.NewRecorder();h.DownloadAttachment(w,r);headers:=map[string]string{};for k,v:=range w.Result().Header{if strings.ToLower(k)!="content-length"{headers[strings.ToLower(k)]=v[0]}}
 return map[string]any{"status":w.Code,"headers":headers,"body":w.Body.String(),"calls":calls,"db_calls":q.calls,"closed":closed}
}
