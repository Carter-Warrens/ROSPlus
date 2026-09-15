SHELL := /bin/bash
.PHONY: all build test check clean deps
all: build
build:
	cargo build --manifest-path crates/Cargo.toml
	cd pkg && go build -o ../build/turbo ./cmd/turbo
	cd frontend && npm run build
check:
	cargo fmt --all --manifest-path crates/Cargo.toml --check
	cargo clippy --manifest-path crates/Cargo.toml --all-targets -- -D warnings
	cd pkg && go vet ./...
	node tooling/validate.mjs
test: build
	./build/turbo test --junit-xml build/test-results.xml
	$(MAKE) check
deps:
	cd frontend && npm ci --no-fund --no-audit
	cd tooling && npm ci --no-fund --no-audit
clean:
	rm -rf build frontend/dist crates/target
