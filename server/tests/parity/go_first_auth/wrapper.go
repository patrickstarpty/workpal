package realtime
import("net/http";"net/http/httptest";"strings";"github.com/gorilla/websocket")
type ParityFirstAuthFixture struct{Raw []byte;Binary,Fragmented,HeaderOnly bool}
func ParityFirstAuth(f ParityFirstAuthFixture)any{
 M=&Metrics{}
 connections:=make(chan *websocket.Conn,1);upgrader:=websocket.Upgrader{}
 server:=httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter,r *http.Request){conn,e:=upgrader.Upgrade(w,r,nil);if e!=nil{panic(e)};connections<-conn}));defer server.Close()
 dialer:=websocket.Dialer{};if f.Fragmented{dialer.WriteBufferSize=16}
 peer,_,err:=dialer.Dial("ws"+strings.TrimPrefix(server.URL,"http"),nil);if err!=nil{panic(err)};defer peer.Close();conn:=<-connections;defer conn.Close();conn.SetReadLimit(inboundReadLimit)
 done:=make(chan any,1);go func(){token,message,closed:=firstMessageAuth(conn);done<-map[string]any{"token":token,"error":message,"closed":closed,"too_large":M.InboundTooLargeTotal.Load()}}()
 if f.HeaderOnly{
  first:=byte(0x81);if f.Binary{first=0x82};mask:=[]byte{'a','b','c','d'}
  if f.Fragmented{prefix:=append([]byte{first&0x7f,0xfe,0x80,0},mask...);for i:=0;i<32768;i++{prefix=append(prefix,'x'^mask[i%4])};peer.UnderlyingConn().Write(prefix);peer.UnderlyingConn().Write(append([]byte{0x80,0xfe,0x80,1},mask...))}else{peer.UnderlyingConn().Write(append([]byte{first,0xff,0,0,0,0,0,1,0,1},mask...))};return <-done
 }
 kind:=websocket.TextMessage;if f.Binary{kind=websocket.BinaryMessage};_ = peer.WriteMessage(kind,f.Raw);return <-done
}
