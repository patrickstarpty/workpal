package main
import("encoding/json";"os";"workpal.local/workpal/server/internal/realtime")
func main(){json.NewEncoder(os.Stdout).Encode(realtime.ParityRedisStop(os.Args[1]))}
