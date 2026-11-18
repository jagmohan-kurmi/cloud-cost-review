from __future__ import annotations

import csv
import json
import statistics
from datetime import date
from pathlib import Path
from typing import Any


ALIASES = {
    "service": ("service", "service_name", "provider_service", "resource"),
    "day": ("day", "date", "usage_date", "billing_date"),
    "cost": ("cost", "amount", "total_cost", "unblended_cost"),
    "tags": ("tags", "resource_tags", "labels"),
}


def parse_tags(raw: str) -> dict[str, str]:
    raw = raw.strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
        if isinstance(value, dict):
            return {str(k): str(v) for k, v in value.items()}
    except json.JSONDecodeError:
        pass
    tags: dict[str, str] = {}
    for item in raw.split(";"):
        if "=" in item:
            key, value = item.split("=", 1)
            tags[key.strip()] = value.strip()
    return tags


def ingest(path: str | Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        handle = open(path, "r", encoding="utf-8-sig", newline="")
    except OSError as exc:
        return rows, [f"cannot read CSV: {exc}"]
    with handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return rows, ["CSV has no header"]
        headers = {name.strip().lower(): name for name in reader.fieldnames}
        resolved: dict[str, str] = {}
        for canonical, aliases in ALIASES.items():
            match = next((headers[a] for a in aliases if a in headers), None)
            if match:
                resolved[canonical] = match
        missing = [name for name in ("service", "day", "cost") if name not in resolved]
        if missing:
            return rows, ["missing required columns: " + ", ".join(missing)]
        for line, raw in enumerate(reader, 2):
            service = (raw.get(resolved["service"]) or "").strip()
            day = (raw.get(resolved["day"]) or "").strip()
            cost_text = (raw.get(resolved["cost"]) or "").strip()
            if not service:
                errors.append(f"row {line}: empty service")
                continue
            try:
                day_value = date.fromisoformat(day)
            except ValueError:
                errors.append(f"row {line}: invalid ISO day {day!r}")
                continue
            try:
                cost = float(cost_text)
            except (TypeError, ValueError):
                errors.append(f"row {line}: invalid cost {cost_text!r}")
                continue
            if cost < 0:
                errors.append(f"row {line}: negative cost")
                continue
            tags_raw = raw.get(resolved["tags"], "") if "tags" in resolved else ""
            rows.append({"service": service, "day": day_value.isoformat(), "cost": cost, "tags": parse_tags(tags_raw or "")})
    return rows, errors


def detect_spikes(rows: list[dict[str, Any]], mad_threshold: float = 3.0, minimum_history: int = 7) -> list[dict[str, Any]]:
    if mad_threshold <= 0:
        raise ValueError("mad_threshold must be positive")
    if minimum_history < 2:
        raise ValueError("minimum_history must be at least 2")
    grouped: dict[str, dict[str, float]] = {}
    for row in rows:
        bucket = grouped.setdefault(row["service"], {})
        bucket[row["day"]] = bucket.get(row["day"], 0.0) + row["cost"]
    findings = []
    for service, daily in grouped.items():
        ordered = sorted(daily)
        for index, day in enumerate(ordered):
            history = [daily[d] for d in ordered[max(0, index - minimum_history):index]]
            if len(history) < minimum_history:
                findings.append({"service": service, "day": day, "cost": daily[day], "status": "insufficient_history", "action": "Continue collecting data; no robust comparison is available.", "confidence": "low"})
                continue
            median = statistics.median(history)
            mad = statistics.median(abs(value - median) for value in history)
            if mad > 0:
                deviation = abs(daily[day] - median) / mad
                spike = deviation >= mad_threshold and daily[day] > median
                status = "review_candidate" if spike else "normal"
            else:
                baseline_floor = max(median * 0.10, 1.0)
                deviation = (daily[day] - median) / baseline_floor
                spike = daily[day] > median and deviation >= mad_threshold
                status = "review_candidate" if spike else "normal"
            action = "Review allocation, tags, recent deployment, scale changes, and provider invoice details." if spike else "No action from this baseline; continue routine review."
            findings.append({"service": service, "day": day, "cost": round(daily[day], 6), "baseline_median": round(median, 6), "mad": round(mad, 6), "status": status, "action": action, "confidence": "medium" if spike else "low"})
    return findings


def markdown_report(findings: list[dict[str, Any]], errors: list[str]) -> str:
    lines = ["# Cloud Cost Review", "", "## Findings", ""]
    for item in findings:
        lines.append(f"- **{item['service']}** `{item['day']}`: {item['status']} — cost {item['cost']:.2f}; confidence {item['confidence']}. {item['action']}")
    if errors:
        lines += ["", "## Input errors", ""]
        lines += [f"- {error}" for error in errors]
    return "\n".join(lines)
