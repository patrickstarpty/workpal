package realtime
import "encoding/base64"
type ParityDeliveryFixture struct{Scope,ID,Exclude,EventID string;Frame []byte;External bool}
type parityDeliverySink struct{calls [][]string}
func(s *parityDeliverySink)DeliverDaemonRuntime(id string,frame []byte,event string){s.calls=append(s.calls,[]string{"daemon",id,base64.StdEncoding.EncodeToString(frame),event})}
func(s *parityDeliverySink)DeliverWecomOutbound(id string,frame []byte,event string){s.calls=append(s.calls,[]string{"wecom",id,base64.StdEncoding.EncodeToString(frame),event})}
func ParityDelivery(f ParityDeliveryFixture)any{
 h:=NewHub();clients:=[]*Client{};for _,id:=range [][2]string{{"w","u"},{"w","v"},{"x","u"}}{c:=&Client{hub:h,workspaceID:id[0],userID:id[1],send:make(chan []byte,8)};h.registerClient(c);clients=append(clients,c)};h.subscribe(clients[0],"chat","c");h.subscribe(clients[1],"custom","c")
 sink:=&parityDeliverySink{calls:[][]string{}};var daemon DaemonRuntimeDeliverer;var wecom WecomOutboundDeliverer;if f.External{daemon=sink;wecom=sink}
 ev:=envelope{Scope:f.Scope,ScopeID:f.ID,WorkspaceID:f.Exclude,EventID:f.EventID,PayloadJSON:string(f.Frame)}
 deliverEnvelope(h,daemon,wecom,ev);deliverEnvelope(h,daemon,wecom,ev)
 frames:=[][]string{};for _,c:=range clients{out:=[]string{};for len(c.send)>0{out=append(out,base64.StdEncoding.EncodeToString(<-c.send))};frames=append(frames,out)}
 return map[string]any{"frames":frames,"external":sink.calls}
}
