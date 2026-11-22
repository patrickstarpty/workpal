package realtime
import("context";"encoding/json";"errors")
type parityFrameAuthorizer struct{mode string;calls [][]string}
func(a *parityFrameAuthorizer)AuthorizeScope(_ context.Context,u,w,s,id string)(bool,error){a.calls=append(a.calls,[]string{u,w,s,id});if a.mode=="error"{return false,errors.New("fixture query outage")};return a.mode=="allow",nil}
func ParityHandleFrame(raw []byte,mode string)map[string]any{h:=NewHub();a:=&parityFrameAuthorizer{mode:mode,calls:[][]string{}};h.SetAuthorizer(a);c:=&Client{hub:h,send:make(chan []byte,4),userID:"u",workspaceID:"w"};h.mu.Lock();h.clients[c]=true;h.mu.Unlock();if mode=="marshal"{var value any;if err:=json.Unmarshal(raw,&value);err!=nil{panic(err)};c.sendJSON(value)}else{c.handleFrame(raw)};var reply any;var wire any;select{case data:=<-c.send:wire=string(data);if err:=json.Unmarshal(data,&reply);err!=nil{panic(err)};default:};return map[string]any{"reply":reply,"raw":wire,"calls":a.calls}}
