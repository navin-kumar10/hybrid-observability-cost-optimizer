#!/usr/bin/env python3
"""Monthly cost report: AWS CUR + DigitalOcean billing -> idle/oversized + log waste.

Reads simplified CSV samples (see samples/), emits Markdown + CSV recommendations.
Stdlib only.
"""
import argparse
import csv
import sys
from pathlib import Path

IDLE_CPU_PCT = 5.0
IDLE_MEM_PCT = 10.0
OVERSIZED_CPU_PCT = 25.0
OVERSIZED_MEM_PCT = 40.0
MIN_HOURS = 100
LOG_COST_PER_GB_MONTH_USD = 5.0
RECOMMENDED_LOG_RETENTION_DAYS = 30


def to_float(v):
    try:
        if v is None or str(v).strip() == "":
            return None
        return float(str(v).strip())
    except (ValueError, TypeError):
        return None


def to_int(v):
    f = to_float(v)
    return int(f) if f is not None else None


def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _norm(row, *keys):
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return ""


def get_resource_id(row):
    return str(_norm(row, "resource_id", "ResourceId", "droplet_id", "name", "resourceId")).strip()


def get_service(row):
    return str(_norm(row, "service", "Service", "name")).strip()


def get_vcpu(row):
    v = to_float(_norm(row, "vcpu", "vcpus", "vCPU", "VCPU"))
    return v


def get_mem_gb(row):
    mem = to_float(_norm(row, "memory_gb"))
    if mem is not None:
        return mem
    mem_mb = to_float(_norm(row, "memory_mb", "MemoryMB"))
    if mem_mb is not None:
        return mem_mb / 1024.0
    return None


def get_cpu(row):
    return to_float(_norm(row, "avg_cpu_pct", "AvgCPU", "cpu_pct"))


def get_mem_pct(row):
    return to_float(_norm(row, "avg_mem_pct", "AvgMem", "mem_pct"))


def get_cost(row):
    return to_float(_norm(row, "cost_usd", "UnblendedCost", "cost")) or 0.0


def get_hours(row):
    h = to_float(_norm(row, "usage_hours", "UsageHours", "hours"))
    return h if h is not None else 0.0


def classify(row):
    """Return 'idle' | 'oversized' | 'healthy' | 'unknown'."""
    cpu = get_cpu(row)
    mem = get_mem_pct(row)
    hours = get_hours(row)
    vcpu = get_vcpu(row)
    mem_gb = get_mem_gb(row)
    if cpu is None or mem is None or hours < MIN_HOURS:
        return "unknown"
    if cpu < IDLE_CPU_PCT and mem < IDLE_MEM_PCT:
        return "idle"
    size_gate = (
        (vcpu is not None and vcpu >= 2)
        or (mem_gb is not None and mem_gb >= 4)
    )
    if cpu < OVERSIZED_CPU_PCT and mem < OVERSIZED_MEM_PCT and size_gate:
        return "oversized"
    return "healthy"


def analyze_rows(rows, provider):
    recs = []
    for r in rows:
        status = classify(r)
        rid = get_resource_id(r) or "unknown"
        svc = get_service(r) or provider
        cost = get_cost(r)
        cpu = get_cpu(r)
        mem = get_mem_pct(r)
        if status == "idle":
            recs.append(
                {
                    "provider": provider,
                    "resource_id": rid,
                    "service": svc,
                    "issue": "idle",
                    "detail": f"CPU {cpu}% MEM {mem}% over billing window; consider stop/delete or park.",
                    "est_monthly_saving_usd": round(cost, 2),
                    "action": "stop/delete or schedule park",
                }
            )
        elif status == "oversized":
            recs.append(
                {
                    "provider": provider,
                    "resource_id": rid,
                    "service": svc,
                    "issue": "oversized",
                    "detail": f"CPU {cpu}% MEM {mem}% but sized {r.get('instance_type', r.get('size_slug', '?'))}; downsize one tier.",
                    "est_monthly_saving_usd": round(cost * 0.5, 2),
                    "action": "downsize one tier",
                }
            )
    return recs


def analyze_log_cost(daily_gb, retention_days, cost_per_gb_month=LOG_COST_PER_GB_MONTH_USD):
    recs = []
    if daily_gb is None:
        return recs
    if retention_days is not None and retention_days > RECOMMENDED_LOG_RETENTION_DAYS:
        excess = retention_days - RECOMMENDED_LOG_RETENTION_DAYS
        # Stored volume attributable to excess retention ~ daily_gb * excess days;
        # monthly cost of that volume ~ volume * cost_per_gb_month / 30.
        saving = round(daily_gb * excess / 30.0 * cost_per_gb_month, 2)
        recs.append(
            {
                "provider": "observability",
                "resource_id": "loki-retention",
                "service": "Loki",
                "issue": "excessive-retention",
                "detail": f"Retention {retention_days}d vs recommended {RECOMMENDED_LOG_RETENTION_DAYS}d at {daily_gb}GB/day.",
                "est_monthly_saving_usd": saving,
                "action": f"reduce retention to {RECOMMENDED_LOG_RETENTION_DAYS}d; archive to object storage",
            }
        )
    if daily_gb >= 50:
        recs.append(
            {
                "provider": "observability",
                "resource_id": "log-ingestion",
                "service": "Loki/Promtail",
                "issue": "excessive-log-volume",
                "detail": f"Ingestion {daily_gb}GB/day; drop DEBUG, sample health checks.",
                "est_monthly_saving_usd": round(daily_gb * 0.3 / 30.0 * cost_per_gb_month * 30.0, 2),
                "action": "drop DEBUG/TRACE, sample noisy endpoints (see policies/sampling.md)",
            }
        )
    return recs


def total_cost(rows):
    return round(sum(get_cost(r) for r in rows), 2)


def format_markdown(aws_rows, do_rows, recs, daily_gb, retention_days):
    aws_total = total_cost(aws_rows)
    do_total = total_cost(do_rows)
    grand = round(aws_total + do_total, 2)
    saving = round(sum(r["est_monthly_saving_usd"] for r in recs), 2)
    lines = []
    lines.append("# Monthly Cost Report")
    lines.append("")
    lines.append(f"- AWS total: ${aws_total:.2f}")
    lines.append(f"- DigitalOcean total: ${do_total:.2f}")
    lines.append(f"- Combined: ${grand:.2f}")
    lines.append(f"- Log ingestion: {daily_gb} GB/day, retention {retention_days}d")
    lines.append(f"- Estimated potential saving: ${saving:.2f}/mo")
    lines.append("")
    lines.append("## Recommendations")
    lines.append("")
    if not recs:
        lines.append("No waste detected. No action required.")
    else:
        lines.append("| Provider | Resource | Service | Issue | Detail | Saving $/mo | Action |")
        lines.append("|---|---|---|---|---|---|---|")
        for r in sorted(recs, key=lambda x: -x["est_monthly_saving_usd"]):
            lines.append(
                f"| {r['provider']} | {r['resource_id']} | {r['service']} "
                f"| {r['issue']} | {r['detail']} | {r['est_monthly_saving_usd']:.2f} | {r['action']} |"
            )
    lines.append("")
    lines.append("Thresholds: idle CPU<5% and MEM<10%; oversized CPU<25% and MEM<40% with >=2 vCPU or >=4GB; "
                 "logs retention>30d or >=50GB/day. See docs/COST_OPTIMIZATION.md.")
    lines.append("")
    return "\n".join(lines)


def write_recs_csv(recs, path):
    fields = ["provider", "resource_id", "service", "issue", "detail", "est_monthly_saving_usd", "action"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in sorted(recs, key=lambda x: -x["est_monthly_saving_usd"]):
            w.writerow(r)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Generate monthly cost optimization report.")
    p.add_argument("--aws", required=True, help="Path to AWS CUR sample CSV")
    p.add_argument("--do", required=True, help="Path to DigitalOcean billing CSV")
    p.add_argument("--log-daily-gb", type=float, default=10.0)
    p.add_argument("--log-retention-days", type=int, default=30)
    p.add_argument("--out-md", default="COST_REPORT.md")
    p.add_argument("--out-csv", default="recommendations.csv")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    aws_rows = load_csv(args.aws)
    do_rows = load_csv(args.do)
    recs = analyze_rows(aws_rows, "aws") + analyze_rows(do_rows, "do")
    recs += analyze_log_cost(args.log_daily_gb, args.log_retention_days)
    md = format_markdown(aws_rows, do_rows, recs, args.log_daily_gb, args.log_retention_days)
    Path(args.out_md).write_text(md, encoding="utf-8")
    write_recs_csv(recs, args.out_csv)
    print(f"Wrote {args.out_md} and {args.out_csv} ({len(recs)} recommendations)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
