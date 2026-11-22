package realtime
import "sort"
type ParitySubscriptionsFixture struct{Clients []struct{Workspace,User string;Stopped bool};Steps []struct{Op string;Client int;Scope,ID string}}
func paritySortRooms(rooms [][]string){sort.Slice(rooms,func(i,j int)bool{for k:=range rooms[i]{if rooms[i][k]!=rooms[j][k]{return rooms[i][k]<rooms[j][k]}};return false})}
func ParitySubscriptions(f ParitySubscriptionsFixture)any{
 M=&Metrics{};h:=NewHub();clients:=[]*Client{};for _,v:=range f.Clients{c:=&Client{hub:h,workspaceID:v.Workspace,userID:v.User,send:make(chan []byte,1)};c.stopped.Store(v.Stopped);clients=append(clients,c)}
 callbacks:=[][]string{};first:=func(s,i string){callbacks=append(callbacks,[]string{"first",s,i})};last:=func(s,i string){callbacks=append(callbacks,[]string{"last",s,i})};h.SetSubscriptionCallbacks(first,last)
 out:=[]any{};for _,s:=range f.Steps{callbacks=[][]string{};var result any;c:=clients[s.Client]
 switch s.Op{case "register":h.registerClient(c);case "remove":h.removeClient(c);case "subscribe":result=h.subscribe(c,s.Scope,s.ID);case "unsubscribe":result=h.unsubscribe(c,s.Scope,s.ID);case "disable":h.SetSubscriptionCallbacks(nil,nil);case "enable":h.SetSubscriptionCallbacks(first,last)}
 rooms:=[][]string{};for _,r:=range h.LocalScopes(){rooms=append(rooms,[]string{r.Type,r.ID})};paritySortRooms(rooms)
 if s.Op=="remove"{paritySortRooms(callbacks)}
 subs:=[][][]string{};present:=[]bool{};h.mu.RLock();for _,client:=range clients{one:=[][]string{};for r:=range client.subscriptions{one=append(one,[]string{r.Type,r.ID})};paritySortRooms(one);subs=append(subs,one);present=append(present,h.clients[client])};h.mu.RUnlock()
 out=append(out,map[string]any{"result":result,"callbacks":callbacks,"rooms":rooms,"subscriptions":subs,"present":present,"metrics":M.Snapshot()})
 };return out
}
