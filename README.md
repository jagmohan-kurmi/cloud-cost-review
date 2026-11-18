# Cloud Cost Review

An offline, provider-neutral CLI for normalized billing CSV review. It supports common service, day/date, cost/amount, and tag/label column names.

## Use

```powershell
py -3.11 -m pip install -e .
cost-review samples\billing.csv
cost-review samples\billing.csv --mad-threshold 3 --minimum-history 7 --format json --output review.json
```

Required normalized columns are service, day, and cost. Days must be ISO `YYYY-MM-DD`; costs must be finite, non-negative decimal values. Tags may be JSON objects or semicolon-separated `key=value` pairs.

## Robust baseline

For each service, each day's observations are compared with the preceding configurable number of days (default 7). The baseline is the history median and median absolute deviation (MAD). A positive MAD candidate requires:

`(cost - median) / MAD >= mad_threshold`

and the cost must exceed the median. When MAD is zero, the tool falls back to a 10% median floor (minimum 1.00 in the cost unit) and compares the increase by this floor. Findings are review candidates, not invoice anomalies or savings recommendations. Confidence and actions are clearly labeled.

## Test

```powershell
py -3.11 -m unittest discover -s tests -v
```
