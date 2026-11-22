package main
import("context";"encoding/json";"errors";"os";"github.com/jackc/pgx/v5";"github.com/jackc/pgx/v5/pgtype";"workpal.local/workpal/server/internal/projectaccess";"workpal.local/workpal/server/internal/util";db "workpal.local/workpal/server/pkg/db/generated")
type fixture struct{Principals []*string;Failure string;Empty bool;Member bool}
type queries struct{fixture;calls []any}
func uid(s string)pgtype.UUID{v,e:=util.ParseUUID(s);if e!=nil{panic(e)};return v}
const w="00000000-0000-0000-0000-0000000000c8"
const p="00000000-0000-0000-0000-000000000065"
const p2="00000000-0000-0000-0000-000000000066"
func(q *queries)record(kind string,user any)error{q.calls=append(q.calls,[]any{kind,user});if q.Failure==kind{return errors.New("database down")};return nil}
func(q *queries)ListPrivateProjectIDs(context.Context,pgtype.UUID)([]pgtype.UUID,error){if e:=q.record("private",nil);e!=nil{return nil,e};if q.Empty{return nil,nil};return []pgtype.UUID{uid(p),uid(p2)},nil}
func(q *queries)GetMemberByUserAndWorkspace(_ context.Context,arg db.GetMemberByUserAndWorkspaceParams)(db.Member,error){if e:=q.record("member",util.UUIDToString(arg.UserID));e!=nil{return db.Member{},e};if arg.UserID.Bytes[15]==4{return db.Member{},pgx.ErrNoRows};role:="member";if arg.UserID.Bytes[15]==5{role="admin"};if arg.UserID.Bytes[15]==6{role="owner"};return db.Member{Role:role},nil}
func(q *queries)ListHiddenProjectIDsForUser(_ context.Context,arg db.ListHiddenProjectIDsForUserParams)([]pgtype.UUID,error){if e:=q.record("hidden",util.UUIDToString(arg.UserID));e!=nil{return nil,e};switch arg.UserID.Bytes[15]{case 1:return nil,nil;case 2:return []pgtype.UUID{uid(p2)},nil};return []pgtype.UUID{uid(p),uid(p2)},nil}
func stringsOf(ids []pgtype.UUID)[]string{if ids==nil{return nil};out:=[]string{};for _,v:=range ids{out=append(out,util.UUIDToString(v))};return out}
func main(){var fixtures []fixture;if e:=json.NewDecoder(os.Stdin).Decode(&fixtures);e!=nil{panic(e)};out:=[]any{};for _,f:=range fixtures{q:=&queries{fixture:f,calls:[]any{}};principals:=[]pgtype.UUID{};for _,s:=range f.Principals{v:=pgtype.UUID{};if s!=nil{v=uid(*s)};principals=append(principals,v)};var h projectaccess.Hidden;var e error;if f.Member{h,e=projectaccess.ForMember(context.Background(),q,uid(w),principals[0])}else{h,e=projectaccess.ForPrincipals(context.Background(),q,uid(w),principals...)};message:="";if e!=nil{message=e.Error()};out=append(out,map[string]any{"ids":stringsOf(h.IDs()),"param":stringsOf(h.Param()),"empty":h.Empty(),"see":[]bool{h.CanSeeProject(uid(p)),h.CanSeeProject(uid(p2)),h.CanSeeProject(pgtype.UUID{})},"calls":q.calls,"error":message})};json.NewEncoder(os.Stdout).Encode(out)}
