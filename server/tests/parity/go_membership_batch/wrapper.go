package realtime
import("context";"time";"errors")
type ParityMembershipFixture struct{IDs [][2]string;States []string;Mode string;CancelDuring bool}
type parityMembershipChecker struct{fixture ParityMembershipFixture;calls [][][2]string;cancel context.CancelFunc}
func(c *parityMembershipChecker)IsMember(ctx context.Context,u,w string)(bool,error){return false,nil}
func(c *parityMembershipChecker)Members(ctx context.Context,ids []MembershipIdentity)(map[MembershipIdentity]bool,error){
 call:=[][2]string{};for _,id:=range ids{call=append(call,[2]string{id.WorkspaceID,id.UserID})};c.calls=append(c.calls,call)
 if c.fixture.CancelDuring&&c.cancel!=nil{c.cancel()}
 if c.fixture.Mode=="error"{return nil,errors.New("query unavailable")}
 members:=map[MembershipIdentity]bool{};for _,id:=range ids{if c.fixture.Mode=="allow"{members[id]=true}};return members,nil
}
func ParityMembership(f ParityMembershipFixture)any{
 h:=NewHub();requests:=[]membershipWriteRequest{};results:=[]chan bool{};cancels:=[]context.CancelFunc{}
 for i,id:=range f.IDs{deadline:=time.Now().Add(time.Minute);if f.States[i]=="expired"{deadline=time.Now().Add(-time.Second)};ctx,cancel:=context.WithDeadline(context.Background(),deadline);cancels=append(cancels,cancel);if f.States[i]=="cancelled"{cancel()};ch:=make(chan bool,1);results=append(results,ch);requests=append(requests,membershipWriteRequest{identity:MembershipIdentity{WorkspaceID:id[0],UserID:id[1]},ctx:ctx,result:ch})}
 checker:=&parityMembershipChecker{fixture:f,calls:[][][2]string{}};if len(cancels)>0{checker.cancel=cancels[0]};if f.Mode!="missing"{h.SetMembershipChecker(checker)}
 h.checkWriteMembership(requests)
 out:=[]bool{};for _,ch:=range results{out=append(out,<-ch)};for _,cancel:=range cancels{cancel()}
 return map[string]any{"results":out,"calls":checker.calls}
}
