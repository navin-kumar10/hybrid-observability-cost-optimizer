# Sampling policy

Goal: keep 100% of **signals that matter** (errors, slow, high-value tenants),
sample the rest. Telemetry volume is a cost driver.

## Logs (Promtail / OTel)

- Drop `DEBUG`/`TRACE` at the agent (`promtail/config.yaml` `drop` stages). Re-enable
  per-service temporarily with a label selector, never globally.
- Drop health-check noise: `GET /healthz`, kube-probes.
- Keep: `ERROR`, slow requests (>800ms), audit/security events at 100%.

## Traces (OTel collector `tail_sampling`)

Configured in `otel/collector.yaml`:

| Policy | Keeps |
|---|---|
| `errors` (status ERROR) | 100% |
| `slow` (>800ms) | 100% |
| `probabilistic` | 10% of remaining |

- `dev`: 100% (low volume, debugging).
- `staging`: 25% baseline + 100% errors/slow.
- `prod`: 10% baseline + 100% errors/slow. Raise only during incidents.

## Metrics

- Do not sample metrics; instead drop high-cardinality labels (`user_id`, `request_id`)
  via `metric_relabel_configs` and increase `scrape_interval` for cheap jobs (30-60s).
- Recording rules for SLO burn; raw high-frequency data expires with retention.

## Verifying

- Alert `TraceDropHigh` fires if the collector drops spans (queue full → scale up, don't just sample more).
- Monthly: check `COST_REPORT.md` log-volume recommendation; if `>=50GB/day`, tighten drops first.
