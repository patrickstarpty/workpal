package realtime
import("encoding/base64";"net/http";"net/http/httptest";"strings";"time";"github.com/gorilla/websocket")
func ParityKeepalive(pong bool)any{
 connections:=make(chan *websocket.Conn,1);upgrader:=websocket.Upgrader{}
 server:=httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter,r *http.Request){conn,e:=upgrader.Upgrade(w,r,nil);if e!=nil{panic(e)};connections<-conn}));defer server.Close()
 peer,_,err:=websocket.DefaultDialer.Dial("ws"+strings.TrimPrefix(server.URL,"http"),nil);if err!=nil{panic(err)};defer peer.Close();conn:=<-connections;defer conn.Close()
 h:=NewHub();c:=&Client{hub:h,conn:conn,workspaceID:"w",userID:"u",send:make(chan []byte,256)};h.registerClient(c)
 start:=time.Now();readerDone,writerDone:=make(chan bool),make(chan bool);go func(){c.readPump();close(readerDone)}();go func(){c.writePump();close(writerDone)}()
 // Control the unregister boundary so the read-error TCP close occurs before
 // closing the writer queue; no race-dependent graceful-close frame.
 go func(){<-h.unregister;<-readerDone;h.removeClient(c)}()
 done:=make(chan bool);defer close(done)
 if pong{go func(){select{case <-done:return;case <-time.After(2*time.Second):peer.WriteControl(websocket.PongMessage,[]byte("unsolicited"),time.Now().Add(time.Second))}}()}
 pings:=[]any{};peer.SetPingHandler(func(payload string)error{pings=append(pings,map[string]any{"payload":base64.StdEncoding.EncodeToString([]byte(payload)),"at":time.Since(start).Seconds()});return nil})
 peer.SetReadDeadline(time.Now().Add(70*time.Second));_,_,e:=peer.ReadMessage();elapsed:=time.Since(start).Seconds();code:=0;if closeError,ok:=e.(*websocket.CloseError);ok{code=closeError.Code};<-readerDone;<-writerDone
 return map[string]any{"pings":pings,"closed_at":elapsed,"close_code":code}
}
