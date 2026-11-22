package realtime

import (
 "context"
 "errors"
 "time"
 "github.com/redis/go-redis/v9"
)
type ParityShardMaintenanceFixture struct { Enabled bool; TTL int64; Failure string; Missing bool; Stop bool }
type parityShardMaintenanceClient struct { redis.UniversalClient; f ParityShardMaintenanceFixture; calls []any }
func(c *parityShardMaintenanceClient)fail(name string)error { if c.f.Failure==name{return errors.New(name+" failed")};return nil }
func(c *parityShardMaintenanceClient)Exists(ctx context.Context,keys ...string)*redis.IntCmd{c.calls=append(c.calls,[]any{"exists",keys[0]});v:=int64(1);if c.f.Missing{v=0};return redis.NewIntResult(v,c.fail("exists"))}
func(c *parityShardMaintenanceClient)XTrimMinID(ctx context.Context,key,min string)*redis.IntCmd{c.calls=append(c.calls,[]any{"trim",key,min});return redis.NewIntResult(2,c.fail("trim"))}
func(c *parityShardMaintenanceClient)PTTL(ctx context.Context,key string)*redis.DurationCmd{c.calls=append(c.calls,[]any{"pttl",key});v:=time.Duration(c.f.TTL);if v>=0{v*=time.Millisecond};if c.f.Failure=="pttl"{v=0};return redis.NewDurationResult(v,c.fail("pttl"))}
func(c *parityShardMaintenanceClient)PExpire(ctx context.Context,key string,ttl time.Duration)*redis.BoolCmd{c.calls=append(c.calls,[]any{"expire",key,int64(ttl/time.Millisecond)});return redis.NewBoolResult(c.f.Failure!="gone",c.fail("expire"))}
func(c *parityShardMaintenanceClient)Persist(ctx context.Context,key string)*redis.BoolCmd{c.calls=append(c.calls,[]any{"persist",key});return redis.NewBoolResult(c.f.Failure!="gone",c.fail("persist"))}
func(c *parityShardMaintenanceClient)XLen(ctx context.Context,key string)*redis.IntCmd{c.calls=append(c.calls,[]any{"length",key});return redis.NewIntResult(3,c.fail("length"))}
func(c *parityShardMaintenanceClient)Info(ctx context.Context,sections ...string)*redis.StringCmd{c.calls=append(c.calls,[]any{"info",sections[0]});return redis.NewStringResult("used_memory:17\r\nmaxmemory:19\r\nevicted_keys:23\r\n",c.fail(sections[0]))}
func ParityShardMaintenance(f ParityShardMaintenanceFixture)any{
 M=&Metrics{};c:=&parityShardMaintenanceClient{f:f,calls:[]any{}};r:=NewShardedStreamRelay(NewHub(),c,c,ShardedStreamRelayConfig{Shards:2,StreamTTLEnabled:f.Enabled});r.now=func()time.Time{return time.Unix(1000,0)}
 r.streamSeen[0].Store(true);r.ttl.claimRefresh(ShardedStreamKey(0),time.Now());M.SetRedisStreamsWithoutTTL("sharded",7)
 ctx,cancel:=context.WithCancel(context.Background());defer cancel();if f.Stop{cancel()};r.maintainStreams(ctx)
 s:=M.Snapshot();return map[string]any{"calls":c.calls,"seen":[]bool{r.streamSeen[0].Load(),r.streamSeen[1].Load()},"generation":[]uint64{r.streamGeneration[0].Load(),r.streamGeneration[1].Load()},"metrics":s["redis"]}
}
