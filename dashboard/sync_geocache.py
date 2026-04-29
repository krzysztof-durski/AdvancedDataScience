import argparse
import os
from pathlib import Path

from db import query_df
from geocode import geocode_postal_codes, load_cache, normalize_postal_code


def _load_env_file_if_present() -> None:
    """Load KEY=VALUE pairs from repo .env if not already exported."""
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _distinct_postal_codes_from_db() -> list[str]:
    df = query_df("""
        SELECT DISTINCT postal_code
        FROM hospital_locations
        WHERE postal_code IS NOT NULL
    """)
    unique_codes: list[str] = []
    seen: set[str] = set()
    for raw in df["postal_code"].tolist():
        code = normalize_postal_code(raw)
        if code and code not in seen:
            seen.add(code)
            unique_codes.append(code)
    unique_codes.sort()
    return unique_codes


def main() -> None:
    _load_env_file_if_present()

    parser = argparse.ArgumentParser(
        description="Sync DB postal codes into dashboard/geocache.csv",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Append missing postal codes to geocache.csv (lat/lon set to empty).",
    )
    args = parser.parse_args()
    has_geoapify_key = bool(os.getenv("GEOAPIFY_API_KEY", "").strip())

    cache = load_cache()
    db_codes = _distinct_postal_codes_from_db()
    missing = [pc for pc in db_codes if pc not in cache]
    missing_coords = [pc for pc, (lat, lon) in cache.items() if lat is None or lon is None]

    print(f"DB postal codes: {len(db_codes)}")
    print(f"Cache entries: {len(cache)}")
    print(f"Missing in cache: {len(missing)}")
    print(f"Missing coordinates in cache: {len(missing_coords)}")

    if missing:
        preview = ", ".join(missing[:20])
        suffix = " ..." if len(missing) > 20 else ""
        print(f"Missing sample: {preview}{suffix}")
    else:
        print("Cache is already in sync.")

    if args.write and missing:
        # fallthrough handled by combined write target below
        pass
    elif missing or missing_coords:
        print("Run with --write to sync cache and enrich missing coordinates.")

    if args.write:
        write_targets = list(dict.fromkeys(missing + missing_coords))
        if write_targets:
            print(f"Starting write/enrichment for {len(write_targets)} postal codes ...")
            geocode_postal_codes(write_targets)
            if has_geoapify_key:
                print(
                    f"Processed {len(write_targets)} postal codes "
                    f"({len(missing)} new, {len(missing_coords)} with missing coords) "
                    "with Geoapify enrichment."
                )
            else:
                print(
                    f"Processed {len(write_targets)} postal codes "
                    f"({len(missing)} new, {len(missing_coords)} with missing coords)."
                )
                print("Set GEOAPIFY_API_KEY to auto-fill coordinates during --write.")
        else:
            print("Nothing to update. Cache is fully synced and already has coordinates.")


if __name__ == "__main__":
    main()
