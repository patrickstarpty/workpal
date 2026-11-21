package handler

import "workpal.local/workpal/server/internal/attachmentpreview"

func (h *Handler) maxPreviewSizeBytes() int64 {
	return attachmentpreview.EffectiveMaxSizeBytes(h.cfg.MaxPreviewSizeBytes)
}
