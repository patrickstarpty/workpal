package main
import("context";"encoding/json";"errors";"os";"time";"workpal.local/workpal/server/internal/events";"workpal.local/workpal/server/internal/handler";"workpal.local/workpal/server/internal/realtime")
type privateProjectAudience interface{Audience(context.Context,events.Event)([]string,bool,error)}
const audienceResolveTimeout=2*time.Second
func logAudienceFailure(e events.Event,err error){}
type fixture struct{Event events.Event;Mode string;Recipients []string;Private,Failure bool}
type resolver struct{fixture}
func(r resolver)Audience(ctx context.Context,e events.Event)([]string,bool,error){if r.Failure{return nil,false,errors.New("fixture unavailable")};return r.Recipients,r.Private,nil}
type call struct{Scope string `json:"scope"`;ID string `json:"id"`;Exclude []string `json:"exclude"`;Data string `json:"data"`}
type recorder struct{calls []call}
func(r *recorder)BroadcastToScope(s,i string,d []byte){r.calls=append(r.calls,call{s,i,[]string{},string(d)})}
func(r *recorder)BroadcastToWorkspace(i string,d []byte){r.BroadcastToScope("workspace",i,d)}
func(r *recorder)Broadcast(d []byte){r.BroadcastToScope("global","",d)}
func(r *recorder)SendToUser(i string,d []byte,exclude ...string){if exclude==nil{exclude=[]string{}};r.calls=append(r.calls,call{"user",i,exclude,string(d)})}
func prepare(f *fixture){p,_:=f.Event.Payload.(map[string]any);switch f.Mode{
case "invitation_struct":raw,_:=json.Marshal(p["invitation"]);var v handler.InvitationResponse;if err:=json.Unmarshal(raw,&v);err!=nil{panic(err)};p["invitation"]=v
case "member_struct":raw,_:=json.Marshal(p["member"]);var v handler.MemberWithUserResponse;if err:=json.Unmarshal(raw,&v);err!=nil{panic(err)};p["member"]=v
case "invitation_pointer":m:=p["invitation"].(map[string]any);var ptr *string;if v,ok:=m["invitee_user_id"].(string);ok{ptr=&v};m["invitee_user_id"]=ptr
case "revoked_pointer":var ptr *string;if v,ok:=p["invitee_user_id"].(string);ok{ptr=&v};p["invitee_user_id"]=ptr
case "bad_marshal":p["unsupported"]=func(){}
}}
func main(){var fixtures []fixture;if err:=json.NewDecoder(os.Stdin).Decode(&fixtures);err!=nil{panic(err)};results:=[]any{};for _,f:=range fixtures{prepare(&f);realtime.M.Reset();bus:=events.New();r:=&recorder{calls:[]call{}};registerListeners(bus,r,resolver{f});bus.Publish(f.Event);results=append(results,map[string]any{"calls":r.calls,"events":realtime.M.Snapshot()["events_sent_by_type"]})};json.NewEncoder(os.Stdout).Encode(results)}
