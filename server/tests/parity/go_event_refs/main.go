package main
import("encoding/json";"os";_ "workpal.local/workpal/server/ee/projectfolder")
type fixture struct{Type string `json:"type"`;Payload any `json:"payload"`}
func main(){var fixtures []fixture;if err:=json.NewDecoder(os.Stdin).Decode(&fixtures);err!=nil{panic(err)};results:=[]any{};for _,f:=range fixtures{r:=extractEventRefs(f.Type,f.Payload);results=append(results,map[string]any{"project_known":r.projectKnown,"project_id":r.projectID,"issue_id":r.issueID,"comment_id":r.commentID,"autopilot_id":r.autopilotID,"linked_issue_ids":r.linkedIssueIDs})};json.NewEncoder(os.Stdout).Encode(results)}
