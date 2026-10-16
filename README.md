# Hybrid Observability + Cost Optimizer

Centralized **on-prem** monitoring for hybrid cloud (AWS + DigitalOcean + Kubernetes + apps)
with **cloud cost optimization**: idle/oversized detection, log-ingestion/retention
tuning, and monthly cost reports.

> [!WARNING]
> This repo is a **starter**. It runs a single-node observability stack with local
> filesystem storage. It is **not HA** and **not a backup solution** by itself.
> See [docs/RECOVERY.md](docs/RECOVERY.md). For production, add replication
> (Mimir/Cortex, Loki with object storage + replication), off-site snapshots,
> and tested restores.

## Architecture

```
                          ┌────────────────────────────────────────────┐
                          │            ON-PREM OBSERVABILITY STACK     │
                          │              (docker compose)            │
                          │                                            │
  AWS accounts            │  ┌──────────┐  ┌──────┐  ┌────────────┐    │
 ┌──────────────┐         │  │Prometheus│◄─┤ OTEL │◄─┤  Grafana   │    │
 │ CloudWatch   │──┐      │  │  :9090   │  │Collect.│  │   :3000    │    │
 │ Exporter     │  │      │  └────▲─────┘  └──▲──▲──┘  └─▲──▲──▲───┘    │
 └──────────────┘  │      │       │           │  │        │  │  │       │
                   │ TLS  │  ┌────┴─────┐  ┌──┴──┴──┐  ┌──┴──┴──┴──┐    │
  DigitalOcean     │ mTLS │  │ Alertmgr │  │  Loki  │  │  Jaeger   │    │
 ┌──────────────┐  │ +auth│  │  :9093   │  │ :3100  │  │ :16686    │    │
 │ do-exporter  │──┼──────┼─►│ Slack/   │  │ logs   │  │ traces    │    │
 │ / node_exp   │  │      │  │ Email    │  │        │  │           │    │
 └──────────────┘  │      │  └──────────┘  └──▲─────┘  └───────────┘    │
                   │      │                   │                        │
  Kubernetes       │      │  ┌──────────┐  ┌──┴───────┐                │
 ┌──────────────┐  │      │  │Promtail/ │  │  OTEL SDK│                │
 │ kube-state / │──┘      │  │FluentBit │  │ traces   │                │
 │ node-exporter│         │  │  logs ───┼──┘  metrics │                │
 └──────────────┘         │  └──────────┘     logs ───┘                │
                          │                                            │
  Apps (OTEL SDKs) ───────┼─► OTLP :4317/:4318 (TLS + token)           │
                          └────────────────────────────────────────────┘

  Flow: exporters / agents / OTEL SDKs  ──TLS──►  on-prem stack
```

### Services covered

| Layer | Source | How collected |
|---|---|---|
| AWS | EC2, RDS, S3, ELB, billing (CUR) | `cloudwatch-exporter` + CUR CSV in `samples/` / S3 sync + `scripts/cost-report.py` |
| DigitalOcean | Droplets, Volumes, billing CSV | `do-exporter` / node_exporter + DO billing CSV + `scripts/cost-report.py` |
| Kubernetes | kube-state-metrics, node-exporter, cadvisor | Prometheus scrape via TLS service account |
| Apps | Any language | OpenTelemetry SDK → OTLP → `otel-collector` → Prometheus / Loki / Jaeger |
| Logs | journald + `/var/log` + K8s | Promtail → Loki |
| Traces | OTEL SDKs | OTLP → collector → Jaeger |

### SLOs (starter)

See [docs/SLOS.md](docs/SLOS.md) and [monitoring/slos.yaml](monitoring/slos.yaml).

| Service | SLO | Target | Alert |
|---|---|---|---|
| API availability | 99.9% 2xx/3xx over 30d | burn-rate fast+slow | `SLOBurnFast`, `SLOBurnSlow` |
| API latency p99 | < 600ms over 30d | burn | `LatencySLOBurn` |
| Log pipeline | 99.5% delivery, <5m lag | lag | `LokiIngestionLag` |
| Trace pipeline | 95% spans ingested, sampling per policy | drop rate | `TraceDropHigh` |

### Security

Remote collection is **deny-by-default**:

- TLS everywhere (Prometheus scrape `tls_config`, OTLP `tls`, Loki push `tls`).
- Auth: bearer token / basic auth, least-privilege scrape users.
- Restricted network: firewall + allowlist scrape CIDRs, no public Grafana.
- Secrets via env files, never committed.

Details: [docs/SECURITY.md](docs/SECURITY.md). Quick check: `./scripts/remote-check.sh`.

### Cost-optimization workflow

```
1. Export costs ──► 2. Detect waste ──► 3. Tune telemetry ──► 4. Report
   AWS CUR          idle (CPU<5%         drop DEBUG logs      scripts/cost-report.py
   DO billing CSV   + MEM<10%)          shorten retention     → COST_REPORT.md
                    oversized           sample traces           + recommendations.csv
                    (CPU<25% &          (see policies/)
                    over-provisioned)
```

Run monthly:

```bash
python3 scripts/cost-report.py \
  --aws samples/aws-cur-sample.csv \
  --do samples/do-billing-sample.csv \
  --log-daily-gb 25 --log-retention-days 60 \
  --out-md COST_REPORT.md --out-csv recommendations.csv
```

Details: [docs/COST_OPTIMIZATION.md](docs/COST_OPTIMIZATION.md).

### Redundancy / backup warning

- Compose stack = **single replica**, filesystem storage (`loki/chunks`, `prometheus/data`).
  Disk loss = data loss.
- Minimum for real use: daily volume snapshots + off-site copy, Loki → S3-compatible
  storage with `retention_period` per [policies/retention.md](policies/retention.md),
  Prometheus snapshots to object storage, Grafana DB backup.
- Full runbook: [docs/RECOVERY.md](docs/RECOVERY.md).

## Quickstart

```bash
cp .env.example .env  # if present, else export secrets (see docs/SECURITY.md)
docker compose -f docker/compose.yml up -d
# Grafana http://localhost:3000 (admin/admin, change immediately)
# Prometheus http://localhost:9090  Alertmanager http://localhost:9093
# Loki http://localhost:3100  Jaeger http://localhost:16686
./scripts/remote-check.sh
python3 scripts/cost-report.py --aws samples/aws-cur-sample.csv \
  --do samples/do-billing-sample.csv --out-md COST_REPORT.md --out-csv recommendations.csv
```

## Layout

```
docker/compose.yml          single-node stack
monitoring/                 prometheus.yml, alerts.yml, slos.yaml
loki/, promtail/            log storage + shipping
alertmanager/               routing
otel/                       collector pipeline
grafana/                    2 dashboards (overview + cost) + provisioning
scripts/                    cost-report.py, remote-check.sh
samples/                    AWS CUR + DO billing samples
policies/                   retention.md, sampling.md
docs/                       SLOS, SECURITY, COST_OPTIMIZATION, RECOVERY
```

## CI

`yamllint` + `promtool check rules/config` + `pytest`. See `.github/workflows/ci.yml`.
