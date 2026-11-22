package handler
import("time";"github.com/jackc/pgx/v5/pgtype";"workpal.local/workpal/server/internal/auth";"workpal.local/workpal/server/internal/storage";"workpal.local/workpal/server/internal/util";db "workpal.local/workpal/server/pkg/db/generated")
type ParityMetadataFixture struct{Store,CDN,PublicURL,URL,Bound string;Stable,Signed,ZeroTime bool;Offset int;Width,Height *int32}
type pmStorage struct{storage.Storage;domain string}
func(s pmStorage)CdnDomain()string{return s.domain}
func ParityMetadata(f ParityMetadataFixture)any{
 h:=&Handler{cfg:Config{PublicURL:f.PublicURL}}
 if f.Store=="local"{h.Storage=&storage.LocalStorage{}}else if f.Store=="remote"{h.Storage=pmStorage{domain:f.CDN}}
 if f.Signed{h.CFSigner=&auth.CloudFrontSigner{}}
 id,_:=util.ParseUUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");w,_:=util.ParseUUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
 a:=db.Attachment{ID:id,WorkspaceID:w,UploaderType:"member",Filename:"报告.pdf",Url:f.URL,ContentType:"application/pdf",SizeBytes:3}
 if !f.ZeroTime{a.CreatedAt=pgtype.Timestamptz{Time:time.Date(2026,11,22,12,30,45,999999999,time.FixedZone("fixture",f.Offset)),Valid:true}}
 switch f.Bound{case "issue_id":a.IssueID=w;case "comment_id":a.CommentID=w;case "chat_session_id":a.ChatSessionID=w;case "chat_message_id":a.ChatMessageID=w;case "task_id":a.TaskID=w;case "source_context_id":a.SourceContextID=w}
 if f.Width!=nil{a.Width=pgtype.Int4{Int32:*f.Width,Valid:true}};if f.Height!=nil{a.Height=pgtype.Int4{Int32:*f.Height,Valid:true}}
 mode:=attachmentURLModeSigned;if f.Stable{mode=attachmentURLModeStable};return h.attachmentToResponse(a,mode)
}
