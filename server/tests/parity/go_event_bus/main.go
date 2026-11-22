package main
import("encoding/json";"os";"workpal.local/workpal/server/internal/events")
func run(name string)any{
 bus:=events.New();trace:=[]string{};counts:=[]int{};original:=map[string]any{}
 switch name{
 case "copy":
  e:=events.Event{Type:"agent:status",WorkspaceID:"workspace",Payload:map[string]any{"value":"old"}}
  bus.Subscribe(e.Type,func(e events.Event){e.Type="changed";e.WorkspaceID="other";e.Payload.(map[string]any)["value"]="new"})
  bus.SubscribeAll(func(e events.Event){trace=append(trace,e.Type+"/"+e.WorkspaceID+"/"+e.Payload.(map[string]any)["value"].(string))})
  bus.Publish(e);original=map[string]any{"type":e.Type,"workspaceID":e.WorkspaceID,"payload":e.Payload}
 case "subscriptions":
  bus.Subscribe("x",func(e events.Event){trace=append(trace,"first");bus.Subscribe("x",func(e events.Event){trace=append(trace,"late")});bus.SubscribeAll(func(e events.Event){trace=append(trace,"late-global")})})
  bus.SubscribeAll(func(e events.Event){trace=append(trace,"global")})
  counts=append(counts,bus.SubscriberCount("x"),bus.SubscriberCount("missing"));bus.Publish(events.Event{Type:"x"});counts=append(counts,bus.SubscriberCount("x"))
  trace=append(trace,"second-publish");bus.Publish(events.Event{Type:"x"});counts=append(counts,bus.SubscriberCount("x"))
 case "reentrant":
  bus.Subscribe("x",func(e events.Event){panic("fixture failure")})
  bus.Subscribe("x",func(e events.Event){trace=append(trace,"outer");bus.Publish(events.Event{Type:"nested"})})
  bus.Subscribe("nested",func(e events.Event){trace=append(trace,"nested")})
  bus.SubscribeAll(func(e events.Event){trace=append(trace,"global:"+e.Type)})
  bus.Publish(events.Event{Type:"x"})
 case "nil-and-global-failure":
  bus.Subscribe("x",nil);bus.SubscribeAll(func(e events.Event){panic("fixture global failure")});bus.SubscribeAll(func(e events.Event){trace=append(trace,"survived")});bus.Publish(events.Event{Type:"x"})
 case "empty":bus.SubscribeAll(func(e events.Event){trace=append(trace,"global:"+e.Type)});bus.Publish(events.Event{})
 }
 return map[string]any{"trace":trace,"counts":counts,"original":original}
}
func main(){var cases []string;if err:=json.NewDecoder(os.Stdin).Decode(&cases);err!=nil{panic(err)};out:=[]any{};for _,name:=range cases{out=append(out,run(name))};if err:=json.NewEncoder(os.Stdout).Encode(out);err!=nil{panic(err)}}
