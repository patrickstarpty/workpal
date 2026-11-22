package main
import("encoding/json";"os";"sync";"workpal.local/workpal/server/internal/realtime")
func main(){var fixtures []bool;if e:=json.NewDecoder(os.Stdin).Decode(&fixtures);e!=nil{panic(e)};out:=make([]any,len(fixtures));var wg sync.WaitGroup;for i,f:=range fixtures{wg.Add(1);go func(i int,f bool){defer wg.Done();out[i]=realtime.ParityKeepalive(f)}(i,f)};wg.Wait();json.NewEncoder(os.Stdout).Encode(out)}
