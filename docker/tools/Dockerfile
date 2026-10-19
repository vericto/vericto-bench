# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
# SPDX-License-Identifier: Apache-2.0
#
# vericto-bench tools: vbench, cpstub, hostmon (Go, static) and engine-eval
# (Rust, static; links vericto-engine, FSL-1.1-ALv2, see THIRD_PARTY.md), plus
# the rules export the stub serves. No compiler ships in the final image.
ARG GO_IMAGE
ARG RUST_IMAGE
ARG ALPINE_IMAGE

FROM ${GO_IMAGE} AS go
ARG GOPROXY=https://proxy.golang.org,direct
ARG VERSION=dev
RUN apk add --no-cache git
WORKDIR /src
COPY go.mod go.sum ./
RUN GOPROXY=${GOPROXY} GOFLAGS=-mod=mod go mod download
COPY cmd ./cmd
COPY internal ./internal
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w -X main.Version=${VERSION}" -o /out/vbench ./cmd/vbench && \
    CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/cpstub ./cmd/cpstub && \
    CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/hostmon ./cmd/hostmon

FROM ${RUST_IMAGE} AS rust
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends libclang-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY engine-eval/Cargo.toml engine-eval/Cargo.lock ./
COPY engine-eval/src ./src
RUN T=$(rustc -vV | sed -n 's/^host: //p') && \
    RUSTFLAGS='-C target-feature=+crt-static' cargo build --locked --release --target "$T" && \
    cp target/"$T"/release/engine-eval /engine-eval && /engine-eval export-rules > /rules.json

FROM ${ALPINE_IMAGE}
RUN apk add --no-cache nftables ca-certificates
COPY --from=go /out/vbench /out/cpstub /out/hostmon /usr/local/bin/
COPY --from=rust /engine-eval /usr/local/bin/engine-eval
COPY --from=rust /rules.json /opt/vericto-bench/rules.json
COPY configs/cpstub/sensitive.json /opt/vericto-bench/sensitive.json
LABEL org.opencontainers.image.source="https://github.com/vericto/vericto-bench" \
      org.opencontainers.image.licenses="Apache-2.0 AND FSL-1.1-ALv2"
