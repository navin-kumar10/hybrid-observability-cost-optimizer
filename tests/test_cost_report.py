"""Tests for scripts/cost-report.py (stdlib only, no pytest plugins needed)."""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import importlib.util

SPEC = importlib.util.spec_from_file_location(
    "cost_report", Path(__file__).resolve().parents[1] / "scripts" / "cost-report.py"
)
cr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cr)


def test_idle_detection():
    rows = [
        {"resource_id": "i-idle", "service": "EC2", "instance_type": "t3.micro",
         "vcpu": "2", "memory_gb": "1", "usage_hours": "720",
         "avg_cpu_pct": "3.0", "avg_mem_pct": "8.0", "cost_usd": "12.50"},
    ]
    recs = cr.analyze_rows(rows, "aws")
    assert len(recs) == 1
    assert recs[0]["issue"] == "idle"
    assert recs[0]["est_monthly_saving_usd"] == 12.50


def test_oversized_detection():
    rows = [
        {"resource_id": "i-big", "service": "EC2", "instance_type": "m5.4xlarge",
         "vcpu": "16", "memory_gb": "64", "usage_hours": "720",
         "avg_cpu_pct": "12.0", "avg_mem_pct": "18.0", "cost_usd": "280.00"},
    ]
    recs = cr.analyze_rows(rows, "aws")
    assert len(recs) == 1
    assert recs[0]["issue"] == "oversized"
    assert recs[0]["est_monthly_saving_usd"] == 140.00


def test_healthy_not_flagged():
    rows = [
        {"resource_id": "i-ok", "service": "EC2", "instance_type": "t3.medium",
         "vcpu": "2", "memory_gb": "4", "usage_hours": "720",
         "avg_cpu_pct": "55.0", "avg_mem_pct": "60.0", "cost_usd": "35.00"},
    ]
    assert cr.analyze_rows(rows, "aws") == []


def test_unknown_when_missing_data():
    rows = [{"resource_id": "bucket", "service": "S3", "cost_usd": "18.30"}]
    assert cr.analyze_rows(rows, "aws") == []


def test_log_retention_recommendation():
    recs = cr.analyze_log_cost(25, 60)
    assert any(r["issue"] == "excessive-retention" for r in recs)


def test_no_log_recommendation_when_lean():
    assert cr.analyze_log_cost(5, 14) == []


def test_sample_files_end_to_end(tmp_path):
    base = Path(__file__).resolve().parents[1]
    aws = cr.load_csv(str(base / "samples" / "aws-cur-sample.csv"))
    do = cr.load_csv(str(base / "samples" / "do-billing-sample.csv"))
    assert len(aws) > 0 and len(do) > 0
    recs = cr.analyze_rows(aws, "aws") + cr.analyze_rows(do, "do")
    # Samples intentionally contain idle + oversized on both providers
    issues = {r["issue"] for r in recs}
    assert "idle" in issues
    assert "oversized" in issues
    md = cr.format_markdown(aws, do, recs, 25, 60)
    assert "# Monthly Cost Report" in md
    out = tmp_path / "recs.csv"
    cr.write_recs_csv(recs, str(out))
    with open(out, newline="", encoding="utf-8") as f:
        assert "est_monthly_saving_usd" in f.readline()
