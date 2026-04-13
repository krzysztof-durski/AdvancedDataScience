#!/usr/bin/env python3
"""Run ICD, OPS and hospital ingestion from DATA folder."""

import argparse
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingest.common import DB_CONFIG, IngestStats, merge_stats
from ingest.hospital_ingest import ingest_hospital_json_files
from ingest.icd_ingest import ingest_icd_to_db
from ingest.ops_ingest import ingest_ops_to_db
from ingest.schema import ensure_schema
from ingest.tracking import mark_processed_file, should_process_file


def _parse_year_filter(value: str | None) -> set[int] | None:
    if not value:
        return None
    years: set[int] = set()
    for raw in value.split(","):
        item = raw.strip()
        if item:
            years.add(int(item))
    return years


def _select_hospital_files(hospital_dir: Path, include_years: set[int] | None, exclude_years: set[int] | None) -> list[Path]:
    files = sorted(hospital_dir.glob("*.json"))
    selected: list[Path] = []
    for f in files:
        parts = f.stem.split("-")
        if len(parts) < 3 or not parts[2].isdigit():
            continue
        year = int(parts[2])
        if include_years and year not in include_years:
            continue
        if exclude_years and year in exclude_years:
            continue
        selected.append(f)
    return selected


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent.parent
    data_dir = root / "DATA"
    parser = argparse.ArgumentParser(description="Run data ingestion phases in deterministic order.")
    parser.add_argument("--icd-path", type=Path, default=data_dir / "ICD-diagnoses.txt")
    parser.add_argument("--ops-path", type=Path, default=data_dir / "OPS-procedures.txt")
    parser.add_argument("--hospital-dir", type=Path, default=data_dir / "json_output")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--include-years", type=str, default=None)
    parser.add_argument("--exclude-years", type=str, default=None)
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--no-track-files", action="store_true")
    return parser.parse_args()


def _print_summary(name: str, stats: IngestStats) -> None:
    print(
        f"{name}: read={stats.read} accepted={stats.accepted} skipped={stats.skipped} "
        f"inserted={stats.inserted} updated={stats.updated} errors={stats.errors}"
    )


def main():
    args = parse_args()
    track_files = not args.no_track_files
    include_years = _parse_year_filter(args.include_years)
    exclude_years = _parse_year_filter(args.exclude_years)
    icd_path = args.icd_path
    ops_path = args.ops_path

    if not icd_path.exists():
        print(f"ICD file not found: {icd_path}")
        sys.exit(1)
    if not ops_path.exists():
        print(f"OPS file not found: {ops_path}")
        sys.exit(1)
    if not args.hospital_dir.exists():
        print(f"Hospital folder not found: {args.hospital_dir}")
        sys.exit(1)

    try:
        import psycopg2
        conn = psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        print(f"Database connection failed: {e}")
        sys.exit(1)

    try:
        ensure_schema(conn)
        if args.dry_run:
            conn.rollback()
            print("Dry-run mode enabled: parse/validation only, no database writes.")

        all_stats: list[IngestStats] = []

        print("Phase 1/3 Ingesting ICD...")
        if track_files and not should_process_file(icd_path, "icd", conn):
            icd_stats = IngestStats(read=1, skipped=1)
            print(f"[ICD] skipped unchanged file: {icd_path}")
        else:
            icd_stats = ingest_icd_to_db(icd_path, conn, batch_size=args.batch_size)
            if not args.dry_run:
                mark_processed_file(icd_path, "icd", conn)
        if not args.dry_run:
            conn.commit()
        _print_summary("ICD", icd_stats)
        all_stats.append(icd_stats)

        print("Phase 2/3 Ingesting OPS...")
        if track_files and not should_process_file(ops_path, "ops", conn):
            ops_stats = IngestStats(read=1, skipped=1)
            print(f"[OPS] skipped unchanged file: {ops_path}")
        else:
            ops_stats = ingest_ops_to_db(ops_path, conn, batch_size=args.batch_size)
            if not args.dry_run:
                mark_processed_file(ops_path, "ops", conn)
        if not args.dry_run:
            conn.commit()
        _print_summary("OPS", ops_stats)
        all_stats.append(ops_stats)

        print("Phase 3/3 Ingesting hospital locations...")
        hospital_files = _select_hospital_files(args.hospital_dir, include_years, exclude_years)
        filtered_files: list[Path] = []
        for f in hospital_files:
            if track_files and not should_process_file(f, "hospital", conn):
                continue
            filtered_files.append(f)
        hospital_stats = ingest_hospital_json_files(filtered_files, conn, batch_size=args.batch_size)
        if not args.dry_run:
            for f in filtered_files:
                mark_processed_file(f, "hospital", conn)
            conn.commit()
        _print_summary("HOSPITAL", hospital_stats)
        all_stats.append(hospital_stats)

        total = merge_stats(all_stats)
        print("Final summary:")
        _print_summary("TOTAL", total)
        if args.dry_run:
            conn.rollback()
        print("Done.")
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        if not args.continue_on_error:
            sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
