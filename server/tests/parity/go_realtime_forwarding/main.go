package main
import("context";"encoding/json";"errors";"os";"time";"workpal.local/workpal/server/internal/events";"workpal.local/workpal/server/internal/realtime")
type privateProjectAudience interface{Audience(context.Context,events.Event)([]string,bool,error)}
const audienceResolveTimeout=2*time.Second
func logAudienceFailure(e events.Event,err error){}
type fixture struct{Event events.Event;Recipients []string;Private bool;Failure bool}
type resolver struct{fixture}
func(r resolver)Audience(ctx context.Context,e events.Event)([]string,bool,error){if r.Failure{return nil,false,errors.New("fixture unavailable")};return r.Recipients,r.Private,nil}
type call struct{Scope string `json:"scope"`;ID string `json:"id"`;Data string `json:"data"`}
type recorder struct{calls []call}
func(r *recorder)BroadcastToScope(s,i string,d []byte){r.calls=append(r.calls,call{s,i,string(d)})}
func(r *recorder)BroadcastToWorkspace(i string,d []byte){r.BroadcastToScope("workspace",i,d)}
func(r *recorder)Broadcast(d []byte){r.BroadcastToScope("global","",d)}
func(r *recorder)SendToUser(i string,d []byte,exclude ...string){r.BroadcastToScope("user",i,d)}
func main(){var fixtures []fixture;if err:=json.NewDecoder(os.Stdin).Decode(&fixtures);err!=nil{panic(err)};results:=[]any{};for _,f:=range fixtures{realtime.M.Reset();bus:=events.New();r:=&recorder{calls:[]call{}};registerListeners(bus,r,resolver{f});bus.Publish(f.Event);results=append(results,map[string]any{"calls":r.calls,"events":realtime.M.Snapshot()["events_sent_by_type"]})};json.NewEncoder(os.Stdout).Encode(results)}
