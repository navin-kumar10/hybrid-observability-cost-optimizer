# Cost optimization

## Workflow (monthly)

1. **Export.** AWS Cost Explorer → CUR CSV (columns per `samples/aws-cur-sample.csv`);
   DO Control Panel → billing CSV (per `samples/do-billing-sample.csv`). Save under `reports/YYYY-MM/`.
2. **Run report.**
   ```bash
   python3 scripts/cost-report.py --aws reports/2026-09/cur.csv \
     --do reports/2026-09/do.csv --log-daily-gb 25 --log-retention-days 60 \
     --out-md reports/2026-09/COST_REPORT.md --out-csv reports/2026-09/recommendations.csv
   ```
3. **Act.** File tickets per recommendation; tag resources `Owner`, `Environment`, `Parkable`.
4. **Tune telemetry** (often the fastest saving): see below.
5. **Review** in the `Cloud Cost Overview` Grafana dashboard.

## Waste detectors (`scripts/cost-report.py`)

| Detector | Rule | Saving estimate |
|---|---|---|
| Idle | CPU <5% **and** MEM <10%, hours ≥100 | 100% of monthly cost |
| Oversized | CPU <25% and MEM <40% with ≥2 vCPU or ≥4GB | 50% (one tier down) |
| Excessive retention | Loki retention >30d | `daily_GB * excess_days/30 * $5` |
| Excessive log volume | ≥50 GB/day | 30% of ingestion cost via drops/sampling |

Thresholds are constants at the top of the script — adjust to your fleet.

## Telemetry savings (biggest lever after idle VMs)

- Drop `DEBUG/TRACE` at Promtail (already configured); each 10GB/day ≈ $50/mo at $5/GB.
- Shorten retention 60d → 30d halves Loki storage; archive compliance logs to S3/Spaces.
- Trace sampling: prod 10% baseline + 100% errors/slow (see `policies/sampling.md`).
- Metrics: drop high-cardinality labels, 30-60s scrape for low-value jobs.

## Idle / oversized playbook

- **Idle dev/staging:** stop or park on schedule (nights/weekends); delete unattached volumes/snapshots.
- **Idle prod:** verify with owner — often a forgotten canary/failover; park, don't delete.
- **Oversized:** downsize one tier, watch SLOs for 1 week, then commit to Savings Plans / Reserved Droplets.
