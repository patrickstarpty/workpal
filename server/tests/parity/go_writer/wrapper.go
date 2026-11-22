package realtime
import("context";"encoding/base64";"fmt";"net/http";"net/http/httptest";"strings";"time";"github.com/gorilla/websocket")
type ParityWriterFixture struct{Count,DenyOn int;Inject,Finish bool;Frames [][]byte}
type parityWriterChecker struct{fixture ParityWriterFixture;client *Client;calls int;injected bool}
func(c *parityWriterChecker)IsMember(ctx context.Context,user,workspace string)(bool,error){return true,nil}
func(c *parityWriterChecker)Members(ctx context.Context,ids []MembershipIdentity)(map[MembershipIdentity]bool,error){
 c.calls++;if c.fixture.Inject&&c.calls==1{c.injected=c.client.trySend([]byte("late"))}
 result:=map[MembershipIdentity]bool{};for _,id:=range ids{result[id]=c.fixture.DenyOn==0||c.calls<c.fixture.DenyOn};return result,nil
}
func ParityWriter(f ParityWriterFixture)any{
 connections:=make(chan *websocket.Conn,1);upgrader:=websocket.Upgrader{}
 server:=httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter,r *http.Request){conn,err:=upgrader.Upgrade(w,r,nil);if err!=nil{panic(err)};connections<-conn}));defer server.Close()
 peer,_,err:=websocket.DefaultDialer.Dial("ws"+strings.TrimPrefix(server.URL,"http"),nil);if err!=nil{panic(err)};defer peer.Close();conn:=<-connections
 h:=NewHub();c:=&Client{hub:h,conn:conn,workspaceID:"w",userID:"u",send:make(chan []byte,256)};checker:=&parityWriterChecker{fixture:f,client:c};h.SetMembershipChecker(checker);h.registerClient(c)
 accepted:=[]bool{};if f.Frames!=nil{f.Count=len(f.Frames)};for i:=0;i<f.Count;i++{raw:=[]byte(fmt.Sprint(i));if f.Frames!=nil{raw=f.Frames[i]};accepted=append(accepted,c.trySend(raw))}
 var afterFinish any;if f.Finish{c.closeSend();afterFinish=c.trySend([]byte("after"))}
 closeCode:=make(chan int,1);frames:=make(chan []string,1);go func(){out:=[]string{};peer.SetReadDeadline(time.Now().Add(5*time.Second));for{kind,raw,e:=peer.ReadMessage();if e!=nil{code:=0;if f.Finish{if ce,ok:=e.(*websocket.CloseError);ok{code=ce.Code}};closeCode<-code;break};if kind!=websocket.TextMessage{panic("unexpected frame type")};value:=string(raw);if f.Frames!=nil{value=base64.StdEncoding.EncodeToString(raw)};out=append(out,value)};frames<-out}()
 if f.Finish{c.writePump()}else{for len(c.send)>0{first,ok:=<-c.send;if !ok||!c.writeBatch(first){break}}}
 conn.Close();received:=<-frames
 return map[string]any{"accepted":accepted,"frames":received,"lookups":checker.calls,"injected":checker.injected,"after_finish":afterFinish,"close_code":<-closeCode}
}
