package realtime

type ParityMetricsStep struct{Op,Key string;Value,Other int64}
func ParityMetrics(steps []ParityMetricsStep)any {m:=&Metrics{};out:=[]any{};for _,s:=range steps{switch s.Op{case "node":m.NodeID.Store(s.Key);case "error":m.SetRedisLastError(s.Key);case "stream":m.ObserveRedisStream(s.Key,s.Value,s.Other);case "ttl":m.SetRedisStreamsWithoutTTL(s.Key,s.Value);case "write":m.RedisXAddTotal.Add(s.Value);m.RedisLastXAddLagMicros.Store(s.Other);case "retention":m.RedisRelayRetentionErrors.Add(s.Value);m.RedisRelayStreamTrimmedTotal.Add(s.Other);case "connected":m.RedisConnected.Store(s.Value!=0);case "reset":m.Reset()};out=append(out,m.Snapshot()["redis"])};return out}
