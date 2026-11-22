# --- Build stage ---
FROM golang:1.27.4-alpine AS builder

RUN apk add --no-cache git

WORKDIR /src

# Cache dependencies
COPY server/go/go.mod server/go/go.sum ./server/go/
RUN cd server/go && go mod download

# Copy server source
COPY server/go/ ./server/go/

# Build binaries
ARG VERSION=dev
ARG COMMIT=unknown
ARG DATE=unknown
RUN cd server/go && CGO_ENABLED=0 go build -ldflags "-s -w -X main.version=${VERSION} -X main.commit=${COMMIT}" -o bin/server ./cmd/server
RUN cd server/go && CGO_ENABLED=0 go build -ldflags "-s -w -X main.version=${VERSION} -X main.commit=${COMMIT} -X main.date=${DATE}" -o bin/workpal ./cmd/workpal
RUN cd server/go && CGO_ENABLED=0 go build -ldflags "-s -w" -o bin/migrate ./cmd/migrate
RUN cd server/go && CGO_ENABLED=0 go build -ldflags "-s -w" -o bin/maintenance ./cmd/maintenance
RUN cd server/go && CGO_ENABLED=0 go build -ldflags "-s -w" -o bin/backfill_task_usage_hourly ./cmd/backfill_task_usage_hourly
RUN cd server/go && CGO_ENABLED=0 go build -ldflags "-s -w" -o bin/backfill_codex_usage_cache ./cmd/backfill_codex_usage_cache

# --- Runtime stage ---
FROM alpine:3.21

RUN apk add --no-cache ca-certificates tzdata

WORKDIR /app

COPY --from=builder /src/server/go/bin/server .
COPY --from=builder /src/server/go/bin/workpal .
COPY --from=builder /src/server/go/bin/migrate .
COPY --from=builder /src/server/go/bin/maintenance .
COPY --from=builder /src/server/go/bin/backfill_task_usage_hourly .
COPY --from=builder /src/server/go/bin/backfill_codex_usage_cache .
COPY server/go/migrations/ ./migrations/
COPY LICENSE NOTICE ./
COPY docker/entrypoint.sh .
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["./entrypoint.sh"]
