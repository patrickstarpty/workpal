package main
import("context";"encoding/json";"errors";"io";"os";"path/filepath";"strings";"workpal.local/workpal/server/internal/storage")
type broken struct{sent bool}
func(b *broken)Read(p []byte)(int,error){if b.sent{return 0,errors.New("fixture read failure")};b.sent=true;return copy(p,[]byte("partial")),nil}
func main(){
 var cases []struct{Op,Key,Data,Type,Filename string;Broken bool}
 if err:=json.NewDecoder(os.Stdin).Decode(&cases);err!=nil{panic(err)}
 root,err:=os.MkdirTemp("","storage-fixture-");if err!=nil{panic(err)};defer os.RemoveAll(root)
 os.Setenv("LOCAL_UPLOAD_DIR",root);os.Setenv("LOCAL_UPLOAD_BASE_URL","https://files.example/")
 store:=storage.NewLocalStorageFromEnv();results:=[]any{}
 for _,c:=range cases{
  var err error;value:=""
  switch c.Op{
   case "upload":var reader io.Reader=strings.NewReader(c.Data);if c.Broken{reader=&broken{}}
    value,err=store.UploadStream(context.Background(),c.Key,reader,999,c.Type,c.Filename)
   case "from-reader":var reader io.Reader=strings.NewReader(c.Data);if c.Broken{reader=&broken{}}
    value,err=store.UploadFromReader(context.Background(),c.Key,reader,c.Type,c.Filename)
   case "read":var reader io.ReadCloser;reader,err=store.GetReader(context.Background(),c.Key)
    if err==nil{data,e:=io.ReadAll(reader);reader.Close();err=e;value=string(data)}
   case "delete":err=store.DeleteObject(context.Background(),c.Key)
   case "fixture-file":err=os.WriteFile(filepath.Join(root,c.Key),[]byte(c.Data),0644)
   case "fixture-dir":err=os.MkdirAll(filepath.Join(root,c.Key),0755)
  }
  files:=map[string]string{};dirs:=[]string{}
  walkerr:=filepath.WalkDir(root,func(path string,d os.DirEntry,e error)error{if e!=nil{return e};if path==root{return nil};rel,_:=filepath.Rel(root,path);if d.IsDir(){dirs=append(dirs,rel)}else{b,e:=os.ReadFile(path);if e!=nil{return e};files[rel]=string(b)};return nil});if walkerr!=nil{panic(walkerr)}
  results=append(results,map[string]any{"ok":err==nil,"value":value,"files":files,"dirs":dirs})
 }
 if err:=json.NewEncoder(os.Stdout).Encode(results);err!=nil{panic(err)}
}
