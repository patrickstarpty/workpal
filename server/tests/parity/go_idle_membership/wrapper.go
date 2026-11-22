package realtime
import("context";"encoding/json";"net/http";"net/http/httptest";"strings";"sync/atomic";"time";"github.com/gorilla/websocket")
type parityIdleChecker struct{calls atomic.Int64}
func(c *parityIdleChecker)IsMember(ctx context.Context,user,workspace string)(bool,error){c.calls.Add(1);return false,nil}
func(c *parityIdleChecker)Members(ctx context.Context,ids []MembershipIdentity)(map[MembershipIdentity]bool,error){c.calls.Add(1);return map[MembershipIdentity]bool{},nil}
func ParityIdleMembership()json.RawMessage{
 connections:=make(chan *websocket.Conn,1);upgrader:=websocket.Upgrader{}
 server:=httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter,r *http.Request){conn,e:=upgrader.Upgrade(w,r,nil);if e!=nil{panic(e)};connections<-conn}));defer server.Close()
 peer,_,err:=websocket.DefaultDialer.Dial("ws"+strings.TrimPrefix(server.URL,"http"),nil);if err!=nil{panic(err)};defer peer.Close();conn:=<-connections;defer conn.Close()
 h:=NewHub();checker:=&parityIdleChecker{};h.SetMembershipChecker(checker);c:=&Client{hub:h,conn:conn,workspaceID:"w",userID:"u",send:make(chan []byte,256)};h.registerClient(c)
 readerDone,writerDone:=make(chan bool,1),make(chan bool,1);go func(){c.readPump();readerDone<-true}();go func(){c.writePump();writerDone<-true}()
 time.Sleep(700*time.Millisecond);before:=checker.calls.Load();c.trySend([]byte(`{"type":"private"}`));<-writerDone
 peer.SetReadDeadline(time.Now().Add(time.Second));_,_,readErr:=peer.ReadMessage();code:=0;if e,ok:=readErr.(*websocket.CloseError);ok{code=e.Code}
 select{case <-h.unregister:case <-time.After(time.Second):panic("readPump did not unregister")};<-readerDone
 raw,_:=json.Marshal(map[string]any{"idle_lookup_count":before,"write_lookup_count":checker.calls.Load(),"close_code":code});return raw
}
