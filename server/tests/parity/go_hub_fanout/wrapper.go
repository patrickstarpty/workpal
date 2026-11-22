package realtime
import "sort"
type ParityFanoutFixture struct{Clients []struct{Workspace,User string;Preload int};Actions []struct{Kind,Scope,ID,Exclude,Frame,EventID string;Client int}}
func ParityFanout(f ParityFanoutFixture)any{
 h:=NewHub();clients:=[]*Client{};for _,v:=range f.Clients{c:=&Client{hub:h,workspaceID:v.Workspace,userID:v.User,send:make(chan []byte,256)};h.registerClient(c);for i:=0;i<v.Preload;i++{c.trySend([]byte("preloaded"))};clients=append(clients,c)}
 before:=[]int64{M.MessagesSentTotal.Load(),M.MessagesDroppedTotal.Load(),M.SlowEvictionsTotal.Load()}
 for _,a:=range f.Actions{switch a.Kind{case "scope":h.BroadcastToScopeDedup(a.Scope,a.ID,[]byte(a.Frame),a.EventID);case "user":h.fanoutUser(a.ID,[]byte(a.Frame),a.Exclude,a.EventID);case "global":h.fanoutAllDedup([]byte(a.Frame),a.Exclude,a.EventID);case "subscribe":h.subscribe(clients[a.Client],a.Scope,a.ID);case "unsubscribe":h.unsubscribe(clients[a.Client],a.Scope,a.ID)}}
 frames:=[][]string{};present:=[]bool{};closed:=[]bool{};for _,c:=range clients{out:=[]string{};for len(c.send)>0{out=append(out,string(<-c.send))};frames=append(frames,out);h.mu.RLock();present=append(present,h.clients[c]);h.mu.RUnlock();closed=append(closed,c.sendClosed)}
 rooms:=[][]string{};for _,r:=range h.LocalScopes(){rooms=append(rooms,[]string{r.Type,r.ID})};sort.Slice(rooms,func(i,j int)bool{if rooms[i][0]==rooms[j][0]{return rooms[i][1]<rooms[j][1]};return rooms[i][0]<rooms[j][0]})
 metrics:=[]int64{M.MessagesSentTotal.Load(),M.MessagesDroppedTotal.Load(),M.SlowEvictionsTotal.Load()};for i:=range metrics{metrics[i]-=before[i]}
 return map[string]any{"frames":frames,"present":present,"send_closed":closed,"rooms":rooms,"metrics":metrics}
}
