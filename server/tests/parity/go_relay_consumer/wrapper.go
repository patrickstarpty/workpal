package realtime
import("context";"time";"errors";"encoding/base64";"github.com/redis/go-redis/v9")
type ParityConsumerFixture struct{Mode string;Enabled bool}
type parityConsumerClient struct{redis.UniversalClient;f ParityConsumerFixture;events [][]any;reads int;cancel context.CancelFunc}
func(c *parityConsumerClient)event(v ...any){c.events=append(c.events,v)}
func(c *parityConsumerClient)XGroupCreateMkStream(ctx context.Context,key,group,start string)*redis.StatusCmd{
 c.event("create",key,group,start)
 if c.f.Mode=="create_error"{return redis.NewStatusResult("",errors.New("create unavailable"))}
 if c.f.Mode=="busy"{return redis.NewStatusResult("",errors.New("BUSYGROUP exists"))}
 return redis.NewStatusResult("OK",nil)
}
func(c *parityConsumerClient)PExpire(ctx context.Context,key string,ttl time.Duration)*redis.BoolCmd{
 c.event("expire",key,int64(ttl));if c.f.Mode=="expiry_error"{return redis.NewBoolResult(false,errors.New("expiry unavailable"))};return redis.NewBoolResult(true,nil)
}
func(c *parityConsumerClient)ZAdd(ctx context.Context,key string,members ...redis.Z)*redis.IntCmd{c.event("register",key,members[0].Member);return redis.NewIntResult(1,nil)}
func(c *parityConsumerClient)XReadGroup(ctx context.Context,a *redis.XReadGroupArgs)*redis.XStreamSliceCmd{
 c.event("read",a.Group,a.Consumer,a.Streams,a.Count,a.Block.Milliseconds());c.reads++
 if c.reads==1{switch c.f.Mode{case "nogroup":return redis.NewXStreamSliceCmdResult(nil,errors.New("NOGROUP lost"));case "nil":return redis.NewXStreamSliceCmdResult(nil,redis.Nil);case "read_error":return redis.NewXStreamSliceCmdResult(nil,errors.New("read unavailable"));case "cancel_error":c.cancel();return redis.NewXStreamSliceCmdResult(nil,errors.New("read unavailable"))}}
 deliveryRead:=1;if c.f.Mode=="nogroup"||c.f.Mode=="nil"||c.f.Mode=="read_error"{deliveryRead=2}
 if c.reads==deliveryRead{return redis.NewXStreamSliceCmdResult([]redis.XStream{{Stream:a.Streams[0],Messages:[]redis.XMessage{
  {ID:"1-0",Values:map[string]any{"payload_json":"{\"type\":\"x\"}","event_id":"e","scope":"daemon_runtime","scope_id":"other"}},
  {ID:"2-0",Values:map[string]any{"event_id":"invalid"}},
  {ID:"3-0",Values:map[string]any{"payload_json":"opaque","event_id":"f"}},
 }}},nil)}
 c.cancel();return redis.NewXStreamSliceCmdResult(nil,context.Canceled)
}
func(c *parityConsumerClient)XAck(ctx context.Context,key,group string,ids ...string)*redis.IntCmd{c.event("ack",key,group,ids[0]);if c.f.Mode=="ack_error"{return redis.NewIntResult(0,errors.New("ack unavailable"))};return redis.NewIntResult(1,nil)}
func(c *parityConsumerClient)XGroupDelConsumer(ctx context.Context,key,group,name string)*redis.IntCmd{c.event("clean",key,group,name);return redis.NewIntResult(0,nil)}
func(c *parityConsumerClient)DeliverDaemonRuntime(id string,frame []byte,eventID string){c.event("deliver",id,base64.StdEncoding.EncodeToString(frame),eventID)}
func ParityConsumer(f ParityConsumerFixture)any{
 ctx,cancel:=context.WithCancel(context.Background());defer cancel()
 c:=&parityConsumerClient{f:f,events:[][]any{},cancel:cancel}
 r:=NewRedisRelayWithClientsAndConfig(nil,c,c,StreamRetentionConfig{StreamTTLEnabled:f.Enabled});r.nodeID="node";r.daemonRuntime=c
 before:=[]int64{M.RedisXReadTotal.Load(),M.RedisXReadErrors.Load(),M.RedisAckTotal.Load(),M.RedisRelayStreamMissingTotal.Load(),M.RedisRelayRetentionErrors.Load()}
 r.runConsumer(ctx,&scopeConsumer{done:make(chan struct{})},ScopeDaemonRuntime,"runtime")
 after:=[]int64{M.RedisXReadTotal.Load(),M.RedisXReadErrors.Load(),M.RedisAckTotal.Load(),M.RedisRelayStreamMissingTotal.Load(),M.RedisRelayRetentionErrors.Load()};for i:=range after{after[i]-=before[i]}
 return map[string]any{"events":c.events,"metrics":after}
}
