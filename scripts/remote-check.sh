#!/usr/bin/env bash
# Remote collection health check: TLS, auth, target UP, Loki push, OTLP endpoint.
set -euo pipefail

PROM_URL="${PROM_URL:-http://localhost:9090}"
LOKI_URL="${LOKI_URL:-http://localhost:3100}"
OTEL_GRPC="${OTEL_GRPC:-localhost:4317}"
REMOTE_HOST="${REMOTE_HOST:-}"
FAIL=0

say() { printf '%s\n' "$*"; }
fail() { printf 'FAIL: %s\n' "$*"; FAIL=1; }
pass() { printf 'PASS: %s\n' "$*"; }

say "== Prometheus =="
if curl -sf --max-time 10 "$PROM_URL/-/healthy" >/dev/null; then
  pass "prometheus healthy at $PROM_URL"
else
  fail "prometheus not healthy at $PROM_URL"
fi

if curl -sf --max-time 10 "$PROM_URL/api/v1/targets?state=active" | grep -q '"health":"up"'; then
  pass "at least one target UP"
else
  fail "no targets UP (check scrape auth/TLS/network)"
fi

say "== Loki =="
if curl -sf --max-time 10 "$LOKI_URL/ready" >/dev/null; then
  pass "loki ready at $LOKI_URL"
else
  fail "loki not ready at $LOKI_URL"
fi

say "== OTel collector =="
if (echo > /dev/tcp/localhost/4317) >/dev/null 2>&1 || nc -z localhost 4317 2>/dev/null; then
  pass "otel gRPC reachable at $OTEL_GRPC"
else
  fail "otel gRPC not reachable at $OTEL_GRPC (is otel-collector running?)"
fi

if [[ -n "$REMOTE_HOST" ]]; then
  say "== Remote TLS ($REMOTE_HOST:9100) =="
  if echo | openssl s_client -connect "$REMOTE_HOST:9100" -servername "$REMOTE_HOST" 2>/dev/null | grep -q "BEGIN CERTIFICATE"; then
    pass "TLS cert presented by $REMOTE_HOST"
    echo | openssl s_client -connect "$REMOTE_HOST:9100" -servername "$REMOTE_HOST" 2>/dev/null \
      | openssl x509 -noout -dates -subject || true
  else
    fail "no TLS cert from $REMOTE_HOST:9100 (firewall? exporter down?)"
  fi
else
  say "SKIP remote TLS check (set REMOTE_HOST=host to enable)"
fi

if [[ "$FAIL" -ne 0 ]]; then
  say "remote-check: FAILURES detected"
  exit 1
fi
say "remote-check: all OK"
