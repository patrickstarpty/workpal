package main
import (
 "context"
 "encoding/json"
 "errors"
 "os"
 "time"
 "github.com/redis/go-redis/v9"
 "workpal.local/workpal/server/internal/auth"
)
type Fixture struct { Disabled bool; User, Workspace, Value, Failure string; Present bool }
type client struct { redis.UniversalClient; f Fixture; calls [][]any }
func (c *client) Get(ctx context.Context,key string)*redis.StringCmd {
 c.calls=append(c.calls,[]any{"get",key})
 if c.f.Failure!="" {return redis.NewStringResult("",errors.New(c.f.Failure))}
 if !c.f.Present{return redis.NewStringResult("",redis.Nil)}
 return redis.NewStringResult(c.f.Value,nil)
}
func (c *client) Set(ctx context.Context,key string,value any,ttl time.Duration)*redis.StatusCmd {
 c.calls=append(c.calls,[]any{"set",key,value,ttl.Seconds()})
 if c.f.Failure!="" {return redis.NewStatusResult("",errors.New(c.f.Failure))}
 return redis.NewStatusResult("OK",nil)
}
func (c *client) Del(ctx context.Context,keys ...string)*redis.IntCmd {
 c.calls=append(c.calls,[]any{"delete",keys[0]})
 if c.f.Failure!="" {return redis.NewIntResult(0,errors.New(c.f.Failure))}
 return redis.NewIntResult(1,nil)
}
func main(){
 var fixtures []Fixture
 if e:=json.NewDecoder(os.Stdin).Decode(&fixtures);e!=nil{panic(e)}
 out:=[]any{}
 for _,f:=range fixtures{
  c:=&client{f:f,calls:[][]any{}}
  var r redis.UniversalClient=c
  if f.Disabled{r=nil}
  cache:=auth.NewMembershipCache(r);ctx:=context.Background()
  hit:=cache.Get(ctx,f.User,f.Workspace)
  cache.Set(ctx,f.User,f.Workspace);cache.Invalidate(ctx,f.User,f.Workspace)
  out=append(out,map[string]any{"hit":hit,"calls":c.calls})
 }
 json.NewEncoder(os.Stdout).Encode(out)
}
