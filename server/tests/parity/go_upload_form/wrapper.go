package handler
import("bytes";"crypto/sha256";"encoding/base64";"encoding/hex";"errors";"io";"fmt";"os";"reflect";"net/http";"net/http/httptest";"strings")
type ParityFormFixture struct{Body,ContentType string;Generate bool;PayloadSize,MetadataSize int64;Field string;Sizes []int64}
func parityFormDigest(reader io.Reader)any{hash:=sha256.New();n,e:=io.Copy(hash,reader);if e!=nil{panic(e)};return map[string]any{"size":n,"sha256":hex.EncodeToString(hash.Sum(nil))}}
type parityZeroReader struct{}
func(parityZeroReader)Read(p []byte)(int,error){clear(p);return len(p),nil}
func ParityForm(f ParityFormFixture)any{
 body,e:=base64.StdEncoding.DecodeString(f.Body);if e!=nil{panic(e)};var input io.Reader=bytes.NewReader(body);if f.Generate{prefix:="--boundary\r\nContent-Disposition: form-data; name=\""+f.Field+"\"; filename=\"a\"\r\n\r\n";middle:="\r\n--boundary\r\nContent-Disposition: form-data; name=\"description\"\r\n\r\n";input=io.MultiReader(strings.NewReader(prefix),io.LimitReader(parityZeroReader{},f.PayloadSize),strings.NewReader(middle),io.LimitReader(parityZeroReader{},f.MetadataSize),strings.NewReader("\r\n--boundary--\r\n"))};if len(f.Sizes)>0{readers:=[]io.Reader{};for i,size:=range f.Sizes{readers=append(readers,strings.NewReader(fmt.Sprintf("--boundary\r\nContent-Disposition: form-data; name=\"other\"; filename=\"%d\"\r\n\r\n",i)),io.LimitReader(parityZeroReader{},size),strings.NewReader("\r\n"))};readers=append(readers,strings.NewReader("--boundary--\r\n"));input=io.MultiReader(readers...)};r:=httptest.NewRequest("POST","http://internal/api/upload-file",input);r.Header.Set("Content-Type",f.ContentType)
 err:=parseUploadForm(httptest.NewRecorder(),r);if r.MultipartForm!=nil{defer func(){if e:=r.MultipartForm.RemoveAll();e!=nil{panic(e)}}()}
 if err!=nil{status:=400;var limit int64;var max *http.MaxBytesError;if errors.As(err,&max){status=413;limit=max.Limit};return map[string]any{"status":status,"limit":limit}}
 values:=map[string]any{};files:=map[string]any{}
 for key,items:=range r.MultipartForm.Value{out:=[]any{};for _,value:=range items{out=append(out,parityFormDigest(bytes.NewBufferString(value)))};values[base64.StdEncoding.EncodeToString([]byte(key))]=out}
 for key,items:=range r.MultipartForm.File{out:=[]any{};for _,file:=range items{reader,e:=file.Open();if e!=nil{panic(e)};digest:=parityFormDigest(reader);_,disk:=reader.(*os.File);if !disk{value:=reflect.ValueOf(reader);if value.Kind()==reflect.Struct{closer:=value.FieldByName("Closer");disk=closer.IsValid()&&!closer.IsNil()}};reader.Close();out=append(out,map[string]any{"filename":base64.StdEncoding.EncodeToString([]byte(file.Filename)),"body":digest,"disk":disk})};files[base64.StdEncoding.EncodeToString([]byte(key))]=out}
 return map[string]any{"status":200,"values":values,"files":files}
}
