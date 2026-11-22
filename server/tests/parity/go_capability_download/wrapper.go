package handler
import("context";"errors";"io";"net/http/httptest";"strings";"github.com/go-chi/chi/v5";db "workpal.local/workpal/server/pkg/db/generated")
type ParityRedemptionFixture struct{ID,Query string;Missing,Storage,OpenFailure bool}
type prStorage struct{pdStorage;fail bool}
func(s prStorage)GetReader(ctx context.Context,key string)(io.ReadCloser,error){if s.fail{*s.calls=append(*s.calls,[]any{"read",key});return nil,errors.New("open failed")};return s.pdStorage.GetReader(ctx,key)}
func ParityRedemption(f ParityRedemptionFixture)any{
 base:=ParityAttachmentLoaderFixture{ID:f.ID,StoredWorkspace:"bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"};if f.Missing{base.Failure="attachment-missing"}
 q:=&pdDB{&palDB{f:base,calls:[]any{}},ParityDownloadsFixture{URL:"object",Filename:"image.png",ContentType:"image/png"}}
 calls:=[]any{};closed:=false;h:=&Handler{Queries:db.New(q),cfg:Config{AttachmentFrameAncestors:[]string{"https://app.example"}}}
 if f.Storage{h.Storage=prStorage{pdStorage{calls:&calls,closed:&closed},f.OpenFailure}}
 r:=httptest.NewRequest("GET","http://internal/api/attachments/id/signed-download?"+f.Query,nil);route:=chi.NewRouteContext();route.URLParams.Add("id",f.ID);r=r.WithContext(context.WithValue(r.Context(),chi.RouteCtxKey,route))
 w:=httptest.NewRecorder();h.DownloadAttachmentWithCapability(w,r)
 headers:=map[string]string{};for k,v:=range w.Result().Header{if strings.ToLower(k)!="content-length"{headers[strings.ToLower(k)]=v[0]}}
 return map[string]any{"status":w.Code,"headers":headers,"body":w.Body.String(),"calls":calls,"db_calls":q.calls,"closed":closed}
}
