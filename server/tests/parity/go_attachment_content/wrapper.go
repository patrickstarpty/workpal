package handler
import("context";"encoding/base64";"errors";"io";"net/http/httptest";"strings";"github.com/go-chi/chi/v5";"github.com/jackc/pgx/v5";"github.com/jackc/pgx/v5/pgconn";"github.com/jackc/pgx/v5/pgtype";"workpal.local/workpal/server/internal/storage";db "workpal.local/workpal/server/pkg/db/generated")
type ParityContentFixture struct{Mime,Filename,Data,Failure string;Size,Limit int64;Available bool;Ancestors []string}
type parityContentDB struct{f ParityContentFixture}
func(d parityContentDB)Exec(context.Context,string,...any)(pgconn.CommandTag,error){panic("unexpected Exec")}
func(d parityContentDB)Query(context.Context,string,...any)(pgx.Rows,error){panic("unexpected Query")}
func(d parityContentDB)QueryRow(_ context.Context,sql string,args ...any)pgx.Row{if !strings.Contains(sql,"name: GetAttachment :one"){panic(sql)};return parityContentRow{f:d.f,id:args[0].(pgtype.UUID),workspace:args[1].(pgtype.UUID)}}
type parityContentRow struct{f ParityContentFixture;id,workspace pgtype.UUID}
func(r parityContentRow)Scan(dest ...any)error{if len(dest)!=17{panic("unexpected attachment columns")};*dest[0].(*pgtype.UUID)=r.id;*dest[1].(*pgtype.UUID)=r.workspace;*dest[6].(*string)=r.f.Filename;*dest[7].(*string)="object-url";*dest[8].(*string)=r.f.Mime;*dest[9].(*int64)=r.f.Size;return nil}
type parityContentStorage struct{storage.Storage;f ParityContentFixture;position,opened,closed int}
func(s *parityContentStorage)KeyFromURL(raw string)string{if raw!="object-url"{panic(raw)};return "key"}
func(s *parityContentStorage)GetReader(_ context.Context,key string)(io.ReadCloser,error){if key!="key"{panic(key)};s.opened++;if s.f.Failure=="open-cancel"{return nil,context.Canceled};if s.f.Failure=="open"{return nil,errors.New("open failure")};return s,nil}
func(s *parityContentStorage)Read(p []byte)(int,error){if s.f.Failure=="read-cancel"{return 0,context.Canceled};if s.f.Failure=="read"{return 0,errors.New("read failure")};if s.position>=len(s.f.Data){return 0,io.EOF};n:=len(p);if n>2{n=2};if n>len(s.f.Data)-s.position{n=len(s.f.Data)-s.position};copy(p,s.f.Data[s.position:s.position+n]);s.position+=n;return n,nil}
func(s *parityContentStorage)Close()error{s.closed++;if s.f.Failure=="close-cancel"{return context.Canceled};if s.f.Failure=="close"{return errors.New("close failure")};return nil}
func ParityContent(f ParityContentFixture)any{
 store:=&parityContentStorage{f:f};h:=&Handler{Queries:db.New(parityContentDB{f}),cfg:Config{MaxPreviewSizeBytes:f.Limit,AttachmentFrameAncestors:f.Ancestors}};if f.Available{h.Storage=store}
 router:=chi.NewRouter();router.Get("/api/attachments/{id}/content",h.GetAttachmentContent)
 r:=httptest.NewRequest("GET","http://internal/api/attachments/11111111-1111-4111-8111-111111111111/content",nil);r.Header.Set("X-Workspace-ID","22222222-2222-4222-8222-222222222222")
 w:=httptest.NewRecorder();router.ServeHTTP(w,r);result:=w.Result();headers:=map[string]string{};for _,key:=range []string{"Content-Type","Content-Length","X-Original-Content-Type","Cache-Control","X-Content-Type-Options","Content-Security-Policy"}{headers[key]=result.Header.Get(key)}
 return map[string]any{"status":result.StatusCode,"headers":headers,"body":base64.StdEncoding.EncodeToString(w.Body.Bytes()),"opened":store.opened,"closed":store.closed,"read":store.position}
}
