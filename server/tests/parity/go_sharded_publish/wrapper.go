package realtime
import("context";"time";"errors";"encoding/base64";"github.com/redis/go-redis/v9")
type ParityPublishFixture struct {Scope,ID,Exclude,EventID string;Frame []byte;Enabled bool;MaxLen int64;Failure string;Count int}
type parityPublishClient struct {redis.UniversalClient;failure string;writes []any;expires []any}
func(c *parityPublishClient)XAdd(ctx context.Context,a *redis.XAddArgs)*redis.StringCmd {
 values:=map[string]string{};for k,v:=range a.Values.(map[string]any){s:=redisString(v);if k=="created_at"{s="<clock>"};values[k]=base64.StdEncoding.EncodeToString([]byte(s))}
 c.writes=append(c.writes,map[string]any{"key":a.Stream,"maxlen":a.MaxLen,"approximate":a.Approx,"values":values})
 if c.failure=="write"{return redis.NewStringResult("",errors.New("write unavailable"))};return redis.NewStringResult("1-0",nil)
}
func(c *parityPublishClient)PExpire(ctx context.Context,key string,ttl time.Duration)*redis.BoolCmd {
 c.expires=append(c.expires,map[string]any{"key":key,"ttl_ns":int64(ttl)})
 if c.failure=="expiry"{return redis.NewBoolResult(false,errors.New("expiry unavailable"))};return redis.NewBoolResult(true,nil)
}
func ParityPublish(f ParityPublishFixture)any {
 c:=&parityPublishClient{failure:f.Failure,writes:[]any{},expires:[]any{}}
 r:=NewShardedStreamRelay(nil,c,c,ShardedStreamRelayConfig{StreamMaxLen:f.MaxLen,StreamTTLEnabled:f.Enabled});r.nodeID="node"
 beforeTotal,beforeErrors,beforeRetention:=M.RedisXAddTotal.Load(),M.RedisXAddErrors.Load(),M.RedisRelayRetentionErrors.Load()
 errs:=[]string{};for i:=0;i<f.Count;i++{err:=r.PublishWithID(f.Scope,f.ID,f.Exclude,f.Frame,f.EventID);s:="";if err!=nil{s=err.Error()};errs=append(errs,s)}
 seen:=[]bool{};for i:=range r.streamSeen{seen=append(seen,r.streamSeen[i].Load())};return map[string]any{"seen":seen,"writes":c.writes,"expires":c.expires,"errors":errs,"metrics":[]int64{M.RedisXAddTotal.Load()-beforeTotal,M.RedisXAddErrors.Load()-beforeErrors,M.RedisRelayRetentionErrors.Load()-beforeRetention}}
}
