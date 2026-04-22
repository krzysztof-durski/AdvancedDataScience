import argparse
import sys
from pathlib import Path

from tqdm import tqdm

from ingest.common import IngestCounters, get_connection, resolve_repo_relative
from ingest.hospital_ingest import (
    discover_hospital_files,
    parse_hospital_file,
    upsert_department_diagnoses,
    upsert_department_procedures,
    upsert_departments,
    upsert_location_rows,
)
from ingest.icd_ingest import parse_icd_file, upsert_icd_rows
from ingest.ops_ingest import parse_ops_file, upsert_ops_rows
from ingest.schema import ensure_schema
from ingest.tracking import file_fingerprint, record_file_result, should_process_file


def _flush_hospital_batch(
    conn,
    location_rows: list,
    dept_rows: list,
    dx_rows: list,
    px_rows: list,
    batch_size: int,
    hosp_c: IngestCounters,
) -> None:
    if not location_rows and not dept_rows and not dx_rows and not px_rows:
        return
    with conn.cursor() as cur:
        inserted, updated = upsert_location_rows(cur, location_rows, batch_size=batch_size)
        hosp_c.inserted += inserted
        hosp_c.updated += updated
        upsert_departments(cur, dept_rows, batch_size=batch_size)
        upsert_department_diagnoses(cur, dx_rows, batch_size=batch_size)
        upsert_department_procedures(cur, px_rows, batch_size=batch_size)
    conn.commit()
    location_rows.clear()
    dept_rows.clear()
    dx_rows.clear()
    px_rows.clear()


def _commit_hospital_tracking(
    conn,
    tracked_success_files: list[tuple[str, int, int, str]],
    tracking_enabled: bool,
) -> None:
    if not tracking_enabled or not tracked_success_files:
        return
    with conn.cursor() as cur:
        for file_path, size_b, mtime_ns, sha256 in tracked_success_files:
            record_file_result(cur, file_path, size_b, mtime_ns, sha256, "success", None)
    conn.commit()
    tracked_success_files.clear()


def parse_year_set(value: str | None) -> set[int] | None:
    if not value:
        return None
    return {int(v.strip()) for v in value.split(",") if v.strip()}


def print_phase(name: str, c: IngestCounters) -> None:
    print(
        f"{name}: read={c.read} accepted={c.accepted} skipped={c.skipped} "
        f"inserted={c.inserted} updated={c.updated} errors={c.errors}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest ICD, OPS and hospital JSON into PostgreSQL")
    parser.add_argument("--icd-path", default="DATA/ICD-diagnoses.txt")
    parser.add_argument("--ops-path", default="DATA/OPS-procedures.txt")
    parser.add_argument("--hospital-dir", default="DATA")
    parser.add_argument("--icd-version-year", type=int, default=2025)
    parser.add_argument("--ops-version-year", type=int, default=2025)
    parser.add_argument("--include-years", default="")
    parser.add_argument("--exclude-years", default="")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-track-files", action="store_true")
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Fail fast on the first unparsable hospital JSON file. "
            "Default behaviour is to skip the file, record it in ingest_files "
            "(status='failed') when tracking is enabled, log it to stderr, and continue."
        ),
    )
    parser.add_argument(
        "--continue-on-error",
        dest="continue_on_error",
        action="store_true",
        help="Deprecated no-op kept for backward compatibility (skipping is now default).",
    )
    parser.add_argument(
        "--failed-log",
        default=None,
        metavar="PATH",
        help=(
            "Optional path to write one failed hospital JSON file per line "
            "('<path>\\t<error>'). Useful when tracking is disabled."
        ),
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable tqdm progress bars (useful for logs or non-interactive pipes)",
    )
    parser.add_argument(
        "--hospital-flush-files",
        type=int,
        default=50,
        metavar="N",
        help=(
            "After N successfully parsed hospital JSON files, upsert and commit hospital_* tables "
            "(reduces memory; avoids losing everything if the process is killed before a commit). "
            "Use 0 to buffer all files until the end (legacy behavior)."
        ),
    )
    args = parser.parse_args()
    show_progress = not args.no_progress

    args.icd_path = resolve_repo_relative(args.icd_path)
    args.ops_path = resolve_repo_relative(args.ops_path)
    args.hospital_dir = resolve_repo_relative(args.hospital_dir)

    include_years = parse_year_set(args.include_years)
    exclude_years = parse_year_set(args.exclude_years)

    conn = get_connection()
    try:
        ensure_schema(conn)
        total = IngestCounters()

        # ICD phase
        icd_rows, icd_c = parse_icd_file(
            args.icd_path, args.icd_version_year, show_progress=show_progress
        )
        if not args.dry_run:
            with conn.cursor() as cur:
                inserted, updated = upsert_icd_rows(cur, icd_rows, batch_size=args.batch_size)
                icd_c.inserted += inserted
                icd_c.updated += updated
            conn.commit()
        total.merge(icd_c)
        print_phase("ICD", icd_c)

        # OPS phase
        ops_rows, ops_c = parse_ops_file(
            args.ops_path, args.ops_version_year, show_progress=show_progress
        )
        if not args.dry_run:
            with conn.cursor() as cur:
                inserted, updated = upsert_ops_rows(cur, ops_rows, batch_size=args.batch_size)
                ops_c.inserted += inserted
                ops_c.updated += updated
            conn.commit()
        total.merge(ops_c)
        print_phase("OPS", ops_c)

        # Hospital phase
        hosp_c = IngestCounters()
        location_rows = []
        dept_rows = []
        dx_rows = []
        px_rows = []
        tracked_success_files: list[tuple[str, int, int, str]] = []
        tracking_enabled = not args.no_track_files and not args.dry_run
        can_skip_by_tracking = tracking_enabled
        if tracking_enabled:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM hospital_locations")
                has_hospital_rows = (cur.fetchone()[0] or 0) > 0
            conn.commit()
            # If hospital tables are empty (e.g. manual truncate) but ingest_files still has
            # successful fingerprints, force reprocessing so source JSON is reloaded.
            if not has_hospital_rows:
                can_skip_by_tracking = False
        hospital_files = list(
            discover_hospital_files(args.hospital_dir, include_years, exclude_years)
        )
        if not hospital_files:
            print(
                "WARNING: No hospital JSON files found under "
                f"{args.hospital_dir!r}. Expected filenames like "
                "'260100023-773287000-2024.json' anywhere under that directory "
                "(see --hospital-dir, --include-years, --exclude-years)."
            )
        failed_log_handle = None
        if args.failed_log:
            failed_log_handle = open(args.failed_log, "w", encoding="utf-8")
        failed_files: list[tuple[str, str]] = []
        parsed_since_flush = 0
        for file_path in tqdm(
            hospital_files,
            desc="Hospital JSON",
            unit="file",
            disable=not show_progress,
        ):
            size_b, mtime_ns, sha256 = file_fingerprint(file_path)
            process_this = True
            if can_skip_by_tracking:
                with conn.cursor() as cur:
                    process_this = should_process_file(cur, str(file_path), size_b, mtime_ns, sha256)
                conn.commit()
            if not process_this:
                hosp_c.skipped += 1
                continue
            try:
                location, depts, dx, px, c = parse_hospital_file(file_path)
                hosp_c.merge(c)
                location_rows.append(location)
                dept_rows.extend(depts)
                dx_rows.extend(dx)
                px_rows.extend(px)
                if tracking_enabled:
                    tracked_success_files.append((str(file_path), size_b, mtime_ns, sha256))
                parsed_since_flush += 1
                flush_n = args.hospital_flush_files
                if (
                    not args.dry_run
                    and flush_n > 0
                    and parsed_since_flush >= flush_n
                ):
                    _flush_hospital_batch(
                        conn,
                        location_rows,
                        dept_rows,
                        dx_rows,
                        px_rows,
                        args.batch_size,
                        hosp_c,
                    )
                    _commit_hospital_tracking(conn, tracked_success_files, tracking_enabled)
                    parsed_since_flush = 0
            except Exception as exc:
                hosp_c.errors += 1
                err_msg = str(exc) or exc.__class__.__name__
                failed_files.append((str(file_path), err_msg))
                # Always surface the failure; tqdm.write keeps the progress bar intact.
                tqdm.write(f"FAILED {file_path}: {err_msg}", file=sys.stderr)
                if failed_log_handle is not None:
                    failed_log_handle.write(f"{file_path}\t{err_msg}\n")
                    failed_log_handle.flush()
                if tracking_enabled:
                    with conn.cursor() as cur:
                        record_file_result(cur, str(file_path), size_b, mtime_ns, sha256, "failed", err_msg)
                    conn.commit()
                if args.strict:
                    raise

        if not args.dry_run:
            _flush_hospital_batch(
                conn,
                location_rows,
                dept_rows,
                dx_rows,
                px_rows,
                args.batch_size,
                hosp_c,
            )
            _commit_hospital_tracking(conn, tracked_success_files, tracking_enabled)
        if failed_log_handle is not None:
            failed_log_handle.close()
        total.merge(hosp_c)
        print_phase("HOSPITAL", hosp_c)
        if failed_files:
            print(
                f"HOSPITAL failed files: {len(failed_files)}"
                + (
                    " (see ingest_files where status='failed' for details)"
                    if tracking_enabled
                    else ""
                )
                + (f"; wrote list to {args.failed_log}" if args.failed_log else "")
            )
        print_phase("TOTAL", total)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

