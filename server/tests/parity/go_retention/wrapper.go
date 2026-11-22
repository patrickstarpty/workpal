package realtime
import "time"
type ParityRetentionFixture struct {Config [5]int64;Enabled bool;Steps []struct{Op string;Key string;At int64}}
func ParityRetention(f ParityRetentionFixture) any {
 c:=StreamRetentionConfig{StreamMaxLen:f.Config[0],TrimHorizon:time.Duration(f.Config[1]),StreamTTL:time.Duration(f.Config[2]),TTLRefreshInterval:time.Duration(f.Config[3]),MaintenanceInterval:time.Duration(f.Config[4]),StreamTTLEnabled:f.Enabled}.withDefaults()
 r:=newStreamTTLRefresher(c.StreamTTL,c.TTLRefreshInterval)
 results:=[]any{}
 for _,s:=range f.Steps {at:=time.Unix(0,s.At);var result any
 switch s.Op {case "claim":result=r.claimRefresh(s.Key,at);case "release":r.releaseRefresh(s.Key,at);case "forget":r.forget(s.Key);case "stale":r.forgetStale(at)}
 results=append(results,result)
 }
 return map[string]any{"config":[]int64{c.StreamMaxLen,int64(c.TrimHorizon),int64(c.StreamTTL),int64(c.TTLRefreshInterval),int64(c.MaintenanceInterval)},"enabled":c.StreamTTLEnabled,"results":results}
}
