package uuid
import("bytes";"time")
type ParityV7Fixture struct{Nanos []int64;Random []byte}
func ParityV7(f ParityV7Fixture)interface{}{
 lastV7time=0;calls:=0;values:=[]string{};failed:=[]bool{}
 original:=timeNow;defer func(){timeNow=original}()
 for _,nano:=range f.Nanos{
  timeNow=func()time.Time{calls++;return time.Unix(0,nano)}
  value,err:=NewV7FromReader(bytes.NewReader(f.Random));failed=append(failed,err!=nil)
  if err!=nil{values=append(values,"")}else{values=append(values,value.String())}
 }
 return map[string]interface{}{"values":values,"failed":failed,"clock_calls":calls}
}
