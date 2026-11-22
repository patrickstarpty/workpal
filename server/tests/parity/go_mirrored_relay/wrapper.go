package realtime
import("context";"errors";"encoding/base64")
type ParityMirrorFixture struct{Scope,ID,Exclude,EventID string;Frame []byte;PrimaryError,MirrorError bool}
type parityMirrorChild struct{node string;fail bool;calls,lifecycle *[]any}
func(r *parityMirrorChild)NodeID()string{return r.node}
func(r *parityMirrorChild)Start(context.Context){*r.lifecycle=append(*r.lifecycle,[]string{"start",r.node});M.NodeID.Store(r.node)}
func(r *parityMirrorChild)Stop(){*r.lifecycle=append(*r.lifecycle,[]string{"stop",r.node})}
func(r *parityMirrorChild)Wait(){*r.lifecycle=append(*r.lifecycle,[]string{"wait",r.node})}
func(r *parityMirrorChild)SetDaemonRuntimeDeliverer(DaemonRuntimeDeliverer){*r.lifecycle=append(*r.lifecycle,[]string{"sink",r.node})}
func(r *parityMirrorChild)BroadcastToScope(string,string,[]byte){}
func(r *parityMirrorChild)BroadcastToWorkspace(string,[]byte){}
func(r *parityMirrorChild)SendToUser(string,[]byte,...string){}
func(r *parityMirrorChild)Broadcast([]byte){}
func(r *parityMirrorChild)PublishWithID(scope,id,exclude string,frame []byte,eventID string)error{*r.calls=append(*r.calls,[]string{r.node,scope,id,exclude,base64.StdEncoding.EncodeToString(frame),eventID});if r.fail{return errors.New(r.node+" failed")};return nil}
func ParityMirror(f ParityMirrorFixture)any{M.Reset();calls,lifecycle:=[]any{},[]any{};p:=&parityMirrorChild{"primary",f.PrimaryError,&calls,&lifecycle};m:=&parityMirrorChild{"mirror",f.MirrorError,&calls,&lifecycle};r:=NewMirroredRelay(p,m);r.Start(context.Background());r.SetDaemonRuntimeDeliverer(nil);err:=r.PublishWithID(f.Scope,f.ID,f.Exclude,f.Frame,f.EventID);message:="";if err!=nil{message=err.Error()};r.Stop();r.Wait();return map[string]any{"calls":calls,"lifecycle":lifecycle,"error":message,"node_id":r.NodeID(),"metric_node_id":M.NodeID.Load(),"metrics":[]int64{M.RedisMirrorPrimaryErrors.Load(),M.RedisMirrorSecondaryErrors.Load(),M.RedisMirrorDivergenceTotal.Load()}}}
