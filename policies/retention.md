# Retention policy

| Data | Default | Rationale |
|---|---|---|
| Prometheus metrics | 30d (`--storage.tsdb.retention.time=30d`) | Covers monthly cost cycle; longer history goes to object-storage snapshots, not local TSDB. |
| Loki logs | 30d (`retention_period: 744h`) | Balances troubleshooting vs ingestion/storage cost. DEBUG/TRACE dropped at Promtail. |
| Jaeger traces | 7d (all-in-one memory/badger) | Raw spans are high-volume; sampled per [sampling](sampling.md). |
| Grafana dashboards | git (infinite) | Dashboards are code in `grafana/`. |
| Billing CSVs / reports | 13 months | Needed for year-over-year monthly reports. Store in S3-compatible bucket with versioning. |

## Changing retention

- Prometheus: edit `docker/compose.yml` retention flag + restart. Expect ~1-2KB/sample/series; monitor `prometheus_tsdb_storage_blocks_bytes`.
- Loki: edit `loki/config.yaml` `limits_config.retention_period` + `compactor.retention_enabled: true`.
  Reducing 60d → 30d roughly halves log storage cost (see `scripts/cost-report.py --log-retention-days`).
- Never increase retention without estimating cost: `daily_GB * days * $/GB`.

## Per-environment overrides

- `dev`: 7d metrics / 7d logs (cheap, ephemeral).
- `staging`: 14d metrics / 14d logs.
- `prod`: 30d metrics / 30d logs; compliance archives → object storage, not Loki.
