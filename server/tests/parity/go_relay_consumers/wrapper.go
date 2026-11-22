package realtime
import("context";"sync";"sort";"github.com/redis/go-redis/v9")
type ParityConsumerStep struct{Op,ID string}
type parityConsumersClient struct{redis.UniversalClient;mu sync.Mutex;counts map[string]int;ready chan bool}
func(c *parityConsumersClient)XGroupCreateMkStream(ctx context.Context,key,group,start string)*redis.StatusCmd{c.mu.Lock();c.counts["create:"+key]++;c.mu.Unlock();return redis.NewStatusResult("OK",nil)}
func(c *parityConsumersClient)ZAdd(ctx context.Context,key string,members ...redis.Z)*redis.IntCmd{return redis.NewIntResult(1,nil)}
func(c *parityConsumersClient)XReadGroup(ctx context.Context,a *redis.XReadGroupArgs)*redis.XStreamSliceCmd{c.ready<-true;<-ctx.Done();return redis.NewXStreamSliceCmdResult(nil,ctx.Err())}
func(c *parityConsumersClient)XGroupDelConsumer(ctx context.Context,key,group,name string)*redis.IntCmd{c.mu.Lock();c.counts["clean:"+key]++;c.mu.Unlock();return redis.NewIntResult(0,nil)}
func ParityConsumers(steps []ParityConsumerStep)any{
 ctx,cancel:=context.WithCancel(context.Background());defer cancel();client:=&parityConsumersClient{counts:map[string]int{},ready:make(chan bool,32)};h:=NewHub();r:=NewRedisRelayWithClients(h,client,client);r.nodeID="node";out:=[]any{}
 for _,step:=range steps{key:=sk("chat",step.ID)
 switch step.Op{case "start":r.mu.Lock();fresh:=!r.stopping&&ctx.Err()==nil&&r.consumers[key]==nil;r.mu.Unlock();r.startConsumer(ctx,"chat",step.ID);if fresh{<-client.ready}
 case "stop":r.mu.Lock();old:=r.consumers[key];r.mu.Unlock();r.stopConsumer("chat",step.ID);if old!=nil{<-old.done}
 case "stop_all":r.Stop();r.Wait()
 case "cancel":cancel();r.Wait()}
 r.mu.Lock();keys:=[]string{};for k:=range r.consumers{keys=append(keys,k.ID)};r.mu.Unlock();sort.Strings(keys)
 client.mu.Lock();counts:=map[string]int{};for k,v:=range client.counts{counts[k]=v};client.mu.Unlock()
 out=append(out,map[string]any{"keys":keys,"counts":counts})
 };cancel();r.Stop();r.Wait();return out
}
