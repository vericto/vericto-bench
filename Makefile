# SPDX-FileCopyrightText: 2026 Vericto S.A.S.
# SPDX-License-Identifier: Apache-2.0
#
#   make images   build the harness images (tools, pgbouncer, proxysql, sysbench, analysis)
#   make test     Go and Python unit tests
#   make lint     gofmt, go vet, bash -n, python compile
#   make smoke    laptop smoke run (NOT FOR PUBLISHED NUMBERS), then clean up
SHELL := /bin/bash
lock = $(shell sed -n 's/^$(1)=//p' versions.lock)
# Official images from a mirror with the same digest (e.g. public.ecr.aws/docker/library).
LIBRARY_MIRROR ?=
lib = $(if $(LIBRARY_MIRROR),$(subst docker.io/library,$(LIBRARY_MIRROR),$(call lock,$(1))),$(call lock,$(1)))
TAG ?= local
GOPROXY ?= https://proxy.golang.org,direct
VERSION ?= $(shell git describe --always --dirty 2>/dev/null || echo dev)
BUILD = docker build --pull=false

.PHONY: images tools pgbouncer proxysql sysbench analysis test lint smoke clean-images

images: tools pgbouncer proxysql sysbench analysis

tools:
	$(BUILD) -f docker/tools/Dockerfile -t vericto-bench/tools:$(TAG) \
	  --build-arg GO_IMAGE=$(call lib,GO_IMAGE) --build-arg RUST_IMAGE=$(call lib,RUST_IMAGE) \
	  --build-arg ALPINE_IMAGE=$(call lib,ALPINE_IMAGE) --build-arg GOPROXY=$(GOPROXY) --build-arg VERSION=$(VERSION) .

pgbouncer:
	$(BUILD) -f docker/pgbouncer/Dockerfile -t vericto-bench/pgbouncer:$(TAG) --build-arg UBUNTU_IMAGE=$(call lib,UBUNTU_IMAGE) \
	  --build-arg PGBOUNCER_VERSION=$(call lock,PGBOUNCER_VERSION) --build-arg PGBOUNCER_SHA256=$(call lock,PGBOUNCER_SHA256) docker/pgbouncer

proxysql:
	$(BUILD) -f docker/proxysql/Dockerfile -t vericto-bench/proxysql:$(TAG) --build-arg UBUNTU_IMAGE=$(call lib,UBUNTU_IMAGE) \
	  --build-arg PROXYSQL_VERSION=$(call lock,PROXYSQL_VERSION) \
	  --build-arg PROXYSQL_DEB_SHA256_ARM64=$(call lock,PROXYSQL_DEB_SHA256_ARM64) \
	  --build-arg PROXYSQL_DEB_SHA256_AMD64=$(call lock,PROXYSQL_DEB_SHA256_AMD64) docker/proxysql

sysbench:
	$(BUILD) -f docker/sysbench/Dockerfile -t vericto-bench/sysbench:$(TAG) --build-arg UBUNTU_IMAGE=$(call lib,UBUNTU_IMAGE) \
	  --build-arg SYSBENCH_APT_VERSION=$(call lock,SYSBENCH_APT_VERSION) docker/sysbench

analysis:
	$(BUILD) -f docker/analysis/Dockerfile -t vericto-bench/analysis:$(TAG) --build-arg UBUNTU_IMAGE=$(call lib,UBUNTU_IMAGE) \
	  --build-arg MATPLOTLIB_APT_VERSION=$(call lock,MATPLOTLIB_APT_VERSION) .

test:
	go test -count=1 ./...
	python3 -m unittest discover -s runner/tests -t runner
	python3 -m unittest discover -s analysis/tests -t analysis

lint:
	test -z "$$(gofmt -l .)" || { gofmt -l .; exit 1; }
	go vet ./...
	for f in host/*.sh terraform/aws/*.sh compose/*.sh; do bash -n "$$f" || exit 1; done
	python3 -m py_compile runner/*.py runner/vbr/*.py analysis/*.py

smoke:
	compose/smoke.sh

clean-images:
	-docker rmi vericto-bench/tools:$(TAG) vericto-bench/pgbouncer:$(TAG) vericto-bench/proxysql:$(TAG) vericto-bench/sysbench:$(TAG) vericto-bench/analysis:$(TAG)
