# Recovery

> [!WARNING]
> The compose stack is **single-node with local volumes**. Treat it as ephemeral
> until you add the backups below.

## What survives a restart vs a disk loss

- Container restart: safe (named volumes `prometheus-data`, `loki-data`, `grafana-data`).
- Host disk loss: **total loss** of metrics/logs/traces unless backed up.

## Minimum production backup

1. **Daily volume snapshots** (host/VM snapshots) + weekly off-site copy. Test restore quarterly.
2. **Prometheus:** `curl -XPOST http://localhost:9090/api/v1/admin/tsdb/snapshot`
   then copy `data/snapshots/` to object storage (S3/Spaces).
3. **Loki:** switch `object_store` to S3-compatible, keep `retention_period: 744h`;
   snapshot `/loki` volume alongside.
4. **Grafana:** back up `grafana-data` (dashboards are also in git under `grafana/dashboards/`).
5. **Configs:** everything in git; secrets in a password manager, never only on the host.

## Restore runbook

1. Provision fresh host, install Docker.
2. `git clone` this repo; restore secrets to `.env`.
3. Restore volumes from snapshot/off-site copy into Docker volumes.
4. `docker compose -f docker/compose.yml up -d`, then `./scripts/remote-check.sh`.
5. Verify: Prometheus targets UP, Grafana datasources green, Loki `ready`, Jaeger UI loads,
   Alertmanager `http://localhost:9093/#/status`.

## HA path (when single-node is not enough)

- Metrics: Mimir/Cortex or Prometheus federation + remote_write to object storage.
- Logs: Loki with S3 storage + 3x replication, or Grafana Cloud Loki.
- Traces: Jaeger with Cassandra/Elasticsearch backend.
- Until then, document the accepted RPO (≈24h with daily snapshots) and RTO (≈2h).
