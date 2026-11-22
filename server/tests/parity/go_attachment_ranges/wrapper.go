package handler
type ParityRangeFixture struct{Header string;Size int64}
func ParityRange(f ParityRangeFixture)any{start,length,outcome:=parseSingleByteRange(f.Header,f.Size);return []int64{start,length,int64(outcome)}}
