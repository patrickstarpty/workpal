package handler
import("strings";"time")
type ParityCapabilityFixture struct{ID,SignID,RawExpiry,SignIntent,Intent,SignatureMode string;Expiry,Now int64}
func ParityCapability(f ParityCapabilityFixture)any{
 now:=time.Unix(0,f.Now);signature:=signAttachmentCapabilityIntent(f.SignID,f.Expiry,f.SignIntent);sig:=signature
 switch f.SignatureMode{case "upper":sig=strings.ToUpper(sig);case "space":sig=sig[:2]+" "+sig[2:];case "short":sig=sig[:62];case "odd":sig=sig[:63];case "bad":sig="xx";case "empty":sig=""}
 return map[string]any{"signature":signature,"path":attachmentCapabilityPath(f.ID,now),"download_path":attachmentDownloadCapabilityPath(f.ID,now),"valid":verifyAttachmentCapability(f.ID,f.RawExpiry,sig,f.Intent,now)}
}
