package realtime
import("context";"time";"github.com/redis/go-redis/v9")
func ParityRedisStop(address string)any{
 write:=redis.NewClient(&redis.Options{Addr:address});defer write.Close()
 read:=redis.NewClient(&redis.Options{Addr:address});defer read.Close()
 ctx:=context.Background();deadline:=time.Now().Add(10*time.Second)
 for {if write.Ping(ctx).Err()==nil{break};if time.Now().After(deadline){panic("redis not ready")};time.Sleep(20*time.Millisecond)}
 relay:=NewRedisRelayWithClients(NewHub(),write,read);relay.nodeID="probe-node"
 relay.startConsumer(ctx,"chat","probe-chat")
 key:=StreamKey("chat","probe-chat");group:="node:"+relay.nodeID
 for {consumers,e:=write.XInfoConsumers(ctx,key,group).Result();if e==nil&&len(consumers)==1{break};if time.Now().After(deadline){panic("consumer not ready")};time.Sleep(time.Millisecond)}
 start:=time.Now();relay.stopConsumer("chat","probe-chat");relay.Wait();elapsed:=time.Since(start).Seconds()
 consumers,e:=write.XInfoConsumers(ctx,key,group).Result();if e!=nil{panic(e)}
 return map[string]any{"stop_seconds":elapsed,"consumers_after_wait":len(consumers),"context_timeout_enabled":read.Options().ContextTimeoutEnabled}
}
