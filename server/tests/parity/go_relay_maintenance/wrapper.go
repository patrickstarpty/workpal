package realtime
import("context";"time";"errors";"sort";"github.com/redis/go-redis/v9")
type ParityMaintenanceFixture struct {Enabled bool;TTL int64;Failure string}
type parityMaintenanceClient struct {redis.UniversalClient;f ParityMaintenanceFixture;calls []any;page int}
func(c *parityMaintenanceClient)XTrimMinID(ctx context.Context,key,min string)*redis.IntCmd {c.calls=append(c.calls,[]any{"trim",key,min});if c.f.Failure=="trim"{return redis.NewIntResult(0,errors.New("trim failed"))};return redis.NewIntResult(2,nil)}
func(c *parityMaintenanceClient)PTTL(ctx context.Context,key string)*redis.DurationCmd {c.calls=append(c.calls,[]any{"pttl",key});if c.f.Failure=="pttl"{return redis.NewDurationResult(0,errors.New("pttl failed"))};v:=time.Duration(c.f.TTL);if v>=0{v*=time.Millisecond};return redis.NewDurationResult(v,nil)}
func(c *parityMaintenanceClient)PExpire(ctx context.Context,key string,ttl time.Duration)*redis.BoolCmd {c.calls=append(c.calls,[]any{"expire",key,int64(ttl/time.Millisecond)});if c.f.Failure=="expire"{return redis.NewBoolResult(false,errors.New("expire failed"))};return redis.NewBoolResult(c.f.Failure!="gone",nil)}
func(c *parityMaintenanceClient)Persist(ctx context.Context,key string)*redis.BoolCmd {c.calls=append(c.calls,[]any{"persist",key});if c.f.Failure=="persist"{return redis.NewBoolResult(false,errors.New("persist failed"))};return redis.NewBoolResult(c.f.Failure!="gone",nil)}
func(c *parityMaintenanceClient)Scan(ctx context.Context,cursor uint64,match string,count int64)*redis.ScanCmd {c.calls=append(c.calls,[]any{"scan",cursor,match,count});c.page++;if c.f.Failure=="scan"&&c.page==2{return redis.NewScanCmdResult(nil,0,errors.New("scan failed"))};if c.page==1{return redis.NewScanCmdResult([]string{"legacy"},7,nil)};return redis.NewScanCmdResult([]string{},0,nil)}
func ParityMaintenance(f ParityMaintenanceFixture)any {
 c:=&parityMaintenanceClient{f:f,calls:[]any{}}
 r:=NewRedisRelayWithClientsAndConfig(NewHub(),c,c,StreamRetentionConfig{StreamTTLEnabled:f.Enabled});r.now=func()time.Time{return time.Unix(1000,123456789)}
 beforeErrors,beforeTrim:=M.RedisRelayRetentionErrors.Load(),M.RedisRelayStreamTrimmedTotal.Load()
 states:=[]any{};for i:=0;i<3;i++{r.sweepLegacyStreams(context.Background());keys:=[]string{};for k:=range r.streamsWithoutTTL{keys=append(keys,k)};sort.Strings(keys);states=append(states,map[string]any{"cursor":r.legacyScanCursor,"without":keys,"errors":M.RedisRelayRetentionErrors.Load()-beforeErrors,"trimmed":M.RedisRelayStreamTrimmedTotal.Load()-beforeTrim})}
 return map[string]any{"calls":c.calls,"states":states}
}
