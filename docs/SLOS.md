# SLOs

Authoritative definitions: [monitoring/slos.yaml](../monitoring/slos.yaml).
Alerts implementing burn rates: [monitoring/alerts.yml](../monitoring/alerts.yml).

## Targets

| SLO | Target | Window | SLI |
|---|---|---|---|
| API availability | 99.9% (prod) | 30d rolling | non-5xx / total |
| API latency p99 | <600ms (prod) | 30d | `histogram_quantile(0.99, ...)` |
| Log pipeline delivery | 99.5% | 7d | received vs dropped/lagging |
| Trace pipeline ingest | 95% post-sampling | 7d | ingested vs dropped |

Per-env: dev 99.0% / 1000ms, staging 99.5% / 800ms, prod 99.9% / 600ms.

## Burn-rate alerting

- **Fast burn** (`SLOBurnFast`): >2% 5xx over 5m → critical, page.
- **Slow burn** (`SLOBurnSlow`): >0.5% 5xx over 1h → warning, ticket.
- **Latency** (`LatencySLOBurn`): p99 >0.6s for 15m → warning.

Tune thresholds after 2-4 weeks of baseline data; update `slos.yaml` first, then alerts.

## Dashboards

- `grafana/dashboards/overview.json`: CPU/mem, 5xx ratio, p99, Loki errors. Use `env` variable for dev/staging/prod.
- Add per-service SLO panels by cloning the 5xx/p99 queries with `service="..."` filters.
