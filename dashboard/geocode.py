import json
import os
import time
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

CACHE_FILE = Path(__file__).parent / "geocache.csv"


def normalize_postal_code(value: str | int | None) -> str | None:
    """Normalize an input to a German 5-digit postal code string."""
    if value is None:
        return None
    code = str(value).strip()
    if not code:
        return None
    if code.isdigit():
        code = code.zfill(5)
    if len(code) != 5 or not code.isdigit():
        return None
    return code


def load_cache() -> dict[str, tuple[float | None, float | None]]:
    if not CACHE_FILE.exists():
        return {}
    df = pd.read_csv(CACHE_FILE, dtype={"postal_code": str})
    result: dict[str, tuple[float | None, float | None]] = {}
    for _, row in df.iterrows():
        postal_code = normalize_postal_code(row["postal_code"])
        if postal_code is None:
            continue
        lat = float(row["lat"]) if pd.notna(row["lat"]) else None
        lon = float(row["lon"]) if pd.notna(row["lon"]) else None
        result[postal_code] = (lat, lon)
    return result


def _save_cache(cache: dict[str, tuple[float | None, float | None]]) -> None:
    rows = [{"postal_code": k, "lat": v[0], "lon": v[1]} for k, v in sorted(cache.items())]
    pd.DataFrame(rows).to_csv(CACHE_FILE, index=False)


def _geoapify_lookup(postal_code: str, api_key: str) -> tuple[float, float] | None:
    query = urllib.parse.urlencode(
        {
            "postcode": postal_code,
            "country": "DE",
            "format": "json",
            "limit": 1,
            "apiKey": api_key,
        }
    )
    url = f"https://api.geoapify.com/v1/geocode/search?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "hospital-dashboard-geocache-sync/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=6) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None
    results = payload.get("results", [])
    if not results:
        return None
    lat = results[0].get("lat")
    lon = results[0].get("lon")
    if lat is None or lon is None:
        return None
    return float(lat), float(lon)


def geocode_postal_codes(
    postal_codes: list[str],
    progress_bar=None,
    status_text=None,
) -> dict[str, tuple[float | None, float | None]]:
    """Resolve postal codes using geocache and optional Geoapify enrichment."""
    cache = load_cache()
    # deduplicate while preserving order, while normalizing to 5-digit format
    to_resolve: list[str] = []
    for postal_code in postal_codes:
        normalized = normalize_postal_code(postal_code)
        if normalized and normalized not in to_resolve:
            to_resolve.append(normalized)

    if not to_resolve:
        return cache

    api_key = os.getenv("GEOAPIFY_API_KEY", "").strip()
    use_geoapify = bool(api_key)

    resolved_count = 0
    attempted_count = 0

    for i, postal_code in enumerate(to_resolve):
        if progress_bar is not None:
            progress_bar.progress((i + 1) / len(to_resolve))
        if status_text is not None:
            source_txt = "Geoapify + cache" if use_geoapify else "local geocache"
            status_text.text(f"Resolving {postal_code} via {source_txt} ({i + 1}/{len(to_resolve)}) …")

        current = cache.get(postal_code)
        if current is None:
            cache[postal_code] = (None, None)
            current = cache[postal_code]

        should_enrich = use_geoapify and (current[0] is None or current[1] is None)
        if should_enrich:
            attempted_count += 1
            try:
                resolved = _geoapify_lookup(postal_code, api_key)
                if resolved is not None:
                    cache[postal_code] = resolved
                    resolved_count += 1
            except Exception:
                # Keep unresolved rows as empty so they can be retried later.
                pass
            time.sleep(0.25)

        if status_text is None and ((i + 1) % 25 == 0 or (i + 1) == len(to_resolve)):
            if use_geoapify:
                print(
                    f"[{i + 1}/{len(to_resolve)}] processed; "
                    f"Geoapify resolved {resolved_count}/{attempted_count} attempted"
                )
            else:
                print(f"[{i + 1}/{len(to_resolve)}] processed from local cache")

        if (i + 1) % 100 == 0:
            _save_cache(cache)

    _save_cache(cache)
    return cache
