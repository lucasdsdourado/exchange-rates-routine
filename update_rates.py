"""Fetch latest USD exchange rates and upsert them into data/rates.csv.

Uses only the Python standard library.
"""

import csv
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API_URL = "https://api.frankfurter.dev/v1/latest?base=USD&symbols=EUR,GBP,BRL"
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RATES_CSV = DATA_DIR / "rates.csv"
SUMMARY_MD = DATA_DIR / "summary.md"
FIELDS = ["date", "currency", "rate", "updated_at"]


def fetch_rates():
    req = urllib.request.Request(API_URL, headers={"User-Agent": "exchange-rates-routine/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    return payload["date"], payload["rates"]


def load_rows():
    if not RATES_CSV.exists():
        return []
    with RATES_CSV.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_rows(rows):
    rows.sort(key=lambda r: (r["date"], r["currency"]))
    tmp = RATES_CSV.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(RATES_CSV)


def upsert(rows, date, rates, updated_at):
    index = {(r["date"], r["currency"]): r for r in rows}
    inserted = updated = 0
    for currency, rate in sorted(rates.items()):
        key = (date, currency)
        if key in index:
            index[key]["rate"] = str(rate)
            index[key]["updated_at"] = updated_at
            updated += 1
        else:
            row = {"date": date, "currency": currency, "rate": str(rate), "updated_at": updated_at}
            rows.append(row)
            index[key] = row
            inserted += 1
    return inserted, updated


def write_summary(rows, run_time):
    latest = {}
    for r in rows:
        cur = latest.get(r["currency"])
        if cur is None or r["date"] > cur["date"]:
            latest[r["currency"]] = r
    lines = [
        "# USD Exchange Rates",
        "",
        f"Last run: {run_time} UTC",
        "",
        "| Currency | Rate (per 1 USD) | Date |",
        "|----------|------------------|------|",
    ]
    for currency in sorted(latest):
        r = latest[currency]
        lines.append(f"| {currency} | {r['rate']} | {r['date']} |")
    with SUMMARY_MD.open("w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def main():
    run_time = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    try:
        date, rates = fetch_rates()
    except Exception as exc:  # network / HTTP / JSON errors
        print(f"Error fetching rates: {exc}", file=sys.stderr)
        return 1

    DATA_DIR.mkdir(exist_ok=True)
    rows = load_rows()
    inserted, updated = upsert(rows, date, rates, run_time)
    save_rows(rows)
    write_summary(rows, run_time)

    print(f"Rates date: {date}")
    print(f"Inserted: {inserted}")
    print(f"Updated: {updated}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
