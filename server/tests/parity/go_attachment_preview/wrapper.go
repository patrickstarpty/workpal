package handler
type ParityPreviewFixture struct{Mime string;Filename string}
func ParityPreview(f ParityPreviewFixture)bool{return isTextPreviewable(f.Mime,f.Filename)}
