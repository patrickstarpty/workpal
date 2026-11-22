package realtime
import("context";"errors";"fmt";"time")
type ParityRemovalFixture struct{Kind,Mode string;Raw []byte;Count int}
type parityRemovalChecker struct{mode string;entered chan bool;release chan struct{}}
func(c *parityRemovalChecker)IsMember(ctx context.Context,u,w string)(bool,error){c.entered<-true;select{case<-ctx.Done():return false,ctx.Err();case<-c.release:};if c.mode=="error"{return false,errors.New("lookup unavailable")};return c.mode=="member",nil}
func(c *parityRemovalChecker)Members(ctx context.Context,ids []MembershipIdentity)(map[MembershipIdentity]bool,error){return nil,nil}
func ParityRemoval(f ParityRemovalFixture)any{
 if f.Kind=="parse"{user,removal:=parseMemberRemoval("w",f.Raw);return map[string]any{"candidate":memberRemovalCandidate(f.Raw),"user":user,"removal":removal}}
 h:=NewHub();checker:=&parityRemovalChecker{mode:f.Mode,entered:make(chan bool,1024),release:make(chan struct{})};h.SetMembershipChecker(checker)
 client:=func(user string)*Client{return &Client{hub:h,workspaceID:"w",userID:user,send:make(chan []byte,1024)}}
 target,peer:=client("u"),client("v");h.registerClient(target);h.registerClient(peer)
 raw:=[]byte(`{"type":"member:removed","payload":{"user_id":"u","workspace_id":"w"}}`)
 handled:=[]bool{};for i:=0;i<f.Count;i++{handled=append(handled,h.queueMemberRemoval("w",raw,fmt.Sprint(i)));if i<2{<-checker.entered}}
 pending:=h.memberRemovalPending.Load();dropped:=h.memberRemovalDropped.Load();late:=client("u");h.registerClient(late)
 frames:=[]string{};for len(peer.send)>0{frames=append(frames,string(<-peer.send))}
 close(checker.release);until:=time.Now().Add(5*time.Second);for h.memberRemovalPending.Load()!=0&&time.Now().Before(until){time.Sleep(time.Millisecond)};if h.memberRemovalPending.Load()!=0{panic("removal workers did not drain")};close(h.memberRemovals)
 return map[string]any{"handled":handled,"pending_before_release":pending,"dropped":dropped,"peer_frames":frames,"target_stopped":target.stopped.Load(),"late_stopped":late.stopped.Load()}
}
