package realtime
func ParityInjectEventID(frame,id []byte)[]byte{return injectEventID(frame,string(id))}
