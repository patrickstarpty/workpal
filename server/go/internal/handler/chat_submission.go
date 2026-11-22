package handler

import (
	"errors"
	"net/http"

	"workpal.local/workpal/server/internal/service"
)

func (h *Handler) writeChatSubmissionError(w http.ResponseWriter, err error) {
	if errors.Is(err, service.ErrChatSubmissionConflict) {
		writeError(w, http.StatusConflict, service.ErrChatSubmissionConflict.Error())
		return
	}
	writeError(w, http.StatusInternalServerError, "failed to read chat submission receipt")
}
