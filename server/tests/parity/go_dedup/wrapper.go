package realtime
import("sync";"sync/atomic")
func ParitySeen(ids []string,concurrent bool)map[string]any{c:=&Client{};results:=[]bool{};var count atomic.Int32;if concurrent{var wg sync.WaitGroup;for _,id:=range ids{wg.Add(1);go func(id string){defer wg.Done();if c.markSeen(id){count.Add(1)}}(id)};wg.Wait()}else{for _,id:=range ids{ok:=c.markSeen(id);results=append(results,ok);if ok{count.Add(1)}}};return map[string]any{"results":results,"first_count":count.Load(),"window":c.seenList,"size":len(c.seenIDs)}}
