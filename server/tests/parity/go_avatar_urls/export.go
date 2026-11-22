package handler
import("os";"time";"workpal.local/workpal/server/internal/storage")
func ParityAvatarURLs(raw,key,base,public string,disabled bool,ttl float64) any {
 os.Setenv("LOCAL_UPLOAD_BASE_URL",base)
 h:=Handler{cfg:Config{PublicURL:public,AttachmentDownloadURLTTL:time.Duration(ttl*float64(time.Second))}}
 if !disabled{h.Storage=storage.NewLocalStorageFromEnv()}
 served,valid:=avatarKeyFromServedURL(raw)
 return map[string]any{"signature":signAvatarKey(key),"path":avatarURLPath(key),"content_type":avatarContentType(key),
  "resolved":h.resolveAvatarURL(raw),"normalized":h.normalizeStoredAvatarURL(raw),"served_key":served,"valid":valid,"max_age":h.avatarRedirectMaxAge()}
}
