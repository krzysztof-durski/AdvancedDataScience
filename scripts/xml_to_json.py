#!/usr/bin/env python3
"""
Convert all *-xml.xml files from DATA/Folders/xml_*/ to JSON or Python dictionaries.

Usage:
  python scripts/xml_to_json.py                    # Convert all, save to DATA/json_YYYY/
  python scripts/xml_to_json.py --year 2024        # Convert only 2024 (one batch)
  ./scripts/convert_xml_by_year.sh                 # Convert all years, one batch per year
  ./scripts/convert_xml_by_year.sh 2024            # Convert only year 2024
  python scripts/xml_to_json.py --dict-only        # Return list of dicts (no file output)
  python scripts/xml_to_json.py --limit 10         # Process only first 10 files (for testing)
  pip install tqdm                                 # For progress bar with % (optional)
  pip install lxml                                 # For malformed XML recovery (optional)
"""

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

# Fix common malformed XML in source data
_NACHNAME_FIX = re.compile(r"<Nachname>([^<]*)</Name>")  # </Name> → </Nachname>
_POSITION_FIX = re.compile(r"<Postition>([^<]*)</Position>")  # Postition → Position
_SP_SCHLUESSEL_FIX = re.compile(r"<SP-Schluessel>([^<]*)</SP_Schluessel>")  # hyphen vs underscore

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


def xml_element_to_dict(element: ET.Element) -> dict | str | list:
    """
    Recursively convert an XML Element to a Python dict.
    Handles: text-only nodes, repeated child tags (→ list), nested structures (→ dict).
    """
    if element is None:
        return {}

    # Build result from children
    children = list(element)
    text = (element.text or "").strip()

    if not children:
        # Leaf node: return text or empty dict
        return text if text else {}

    result: dict[str, Any] = {}
    for child in children:
        tag = child.tag
        value = xml_element_to_dict(child)

        if tag in result:
            # Same tag appears multiple times → make it a list
            existing = result[tag]
            if not isinstance(existing, list):
                result[tag] = [existing]
            result[tag].append(value)
        else:
            result[tag] = value

    # If there's also text content, store it
    if text:
        result["#text"] = text

    return result


def parse_xml_to_dict(filepath: Path) -> dict:
    """Parse an XML file and return it as a nested dict. Fixes common malformed tags before parsing."""
    raw = filepath.read_bytes()
    try:
        raw_str = raw.decode("utf-8")
    except UnicodeDecodeError:
        raw_str = raw.decode("latin-1")  # Some files use Latin-1 despite UTF-8 declaration
    # Fix common typos in source data
    raw_str = _NACHNAME_FIX.sub(r"<Nachname>\1</Nachname>", raw_str)
    raw_str = _POSITION_FIX.sub(r"<Position>\1</Position>", raw_str)
    raw_str = _SP_SCHLUESSEL_FIX.sub(r"<SP-Schluessel>\1</SP-Schluessel>", raw_str)

    try:
        root = ET.fromstring(raw_str)
    except ET.ParseError as err:
        try:
            import lxml.etree as lxml_etree
            parser = lxml_etree.XMLParser(recover=True)
            root = lxml_etree.fromstring(raw_str.encode("utf-8", errors="replace"), parser)
        except ImportError:
            raise err
        except Exception:
            raise err

    return {root.tag: xml_element_to_dict(root)}


def convert_all_xml_to_json(
    data_root: Path,
    output_dir: Path | None = None,
    year_filter: str | None = None,
    limit: int | None = None,
    show_progress: bool = True,
) -> list[dict]:
    """
    Convert all *-xml.xml files to JSON (or return as list of dicts).

    Args:
        data_root: Path to DATA folder (e.g. DATA/)
        output_dir: If set, save JSON files here (e.g. DATA/json_2024/)
        year_filter: If set, only process xml_YYYY folders matching this year
        limit: If set, process only this many files (for testing)
        show_progress: If True, display progress bar with %

    Returns:
        List of dicts: [{"file": path, "data": {...}}, ...]
    """
    folders = data_root / "Folders"
    if not folders.exists():
        raise FileNotFoundError(f"DATA/Folders not found: {folders}")

    # Collect all (filepath, year, output_dir) tuples
    to_process: list[tuple[Path, str, Path | None]] = []
    for xml_dir in sorted(folders.iterdir()):
        if not xml_dir.is_dir() or not xml_dir.name.startswith("xml_"):
            continue

        year = xml_dir.name.replace("xml_", "")
        if year_filter and year != year_filter:
            continue

        out_subdir = None
        if output_dir:
            out_subdir = output_dir / f"json_{year}"
            out_subdir.mkdir(parents=True, exist_ok=True)

        for fp in sorted(xml_dir.glob("*-xml.xml")):
            to_process.append((fp, year, out_subdir))

    if limit:
        to_process = to_process[:limit]

    total = len(to_process)
    results: list[dict] = []
    failed: list[tuple[Path, str]] = []
    use_tqdm = show_progress and HAS_TQDM and total > 0
    iterator = tqdm(to_process, desc="Converting", unit="file") if use_tqdm else to_process

    def _err(msg: str) -> None:
        if use_tqdm:
            tqdm.write(msg, file=sys.stderr)
        else:
            sys.stderr.write(f"\n{msg}\n")
            sys.stderr.flush()

    for i, (fp, year, out_subdir) in enumerate(iterator):
        try:
            data = parse_xml_to_dict(fp)
            results.append({"file": str(fp), "data": data})

            if out_subdir:
                json_path = out_subdir / (fp.stem.replace("-xml", "") + ".json")
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except ET.ParseError as e:
            failed.append((fp, str(e)))
            _err(f"Parse error {fp}: {e}")
        except Exception as e:
            failed.append((fp, str(e)))
            _err(f"Error {fp}: {e}")

        if show_progress and not HAS_TQDM and total > 0:
            pct = 100 * (i + 1) / total
            sys.stderr.write(f"\rConverting: {i + 1}/{total} ({pct:.1f}%)")
            sys.stderr.flush()

    if show_progress and not HAS_TQDM and total > 0:
        sys.stderr.write("\n")
        sys.stderr.flush()

    if failed and total > 0:
        sys.stderr.write(f"Skipped {len(failed)}/{total} files (parse errors). Install lxml for better recovery.\n")

    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Convert hospital XML quality reports to JSON")
    parser.add_argument("--data", default="DATA", help="Path to DATA folder")
    parser.add_argument("--output", "-o", help="Output directory for JSON files (default: DATA/json_YYYY/)")
    parser.add_argument("--year", "-y", help="Process only this year (e.g. 2024)")
    parser.add_argument("--limit", "-n", type=int, help="Process only N files (for testing)")
    parser.add_argument("--dict-only", action="store_true", help="Return dicts only, don't write files")
    parser.add_argument("--no-progress", action="store_true", help="Disable progress bar")
    args = parser.parse_args()

    data_root = Path(args.data)
    output_dir = Path(args.output) if args.output else (data_root / "json_output")
    if not args.dict_only and not args.output:
        output_dir = data_root / "json_output"

    results = convert_all_xml_to_json(
        data_root=data_root,
        output_dir=None if args.dict_only else output_dir,
        year_filter=args.year,
        limit=args.limit,
        show_progress=not args.no_progress,
    )

    print(f"Converted {len(results)} files")
    if args.dict_only and results:
        print("First file keys:", list(results[0]["data"].keys()))


if __name__ == "__main__":
    main()
