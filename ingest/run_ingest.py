#!/usr/bin/env python3
"""Run ICD and OPS ingestion from DATA folder."""

import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingest.common import DB_CONFIG
from ingest.icd_ingest import ingest_icd_to_db
from ingest.ops_ingest import ingest_ops_to_db


def main():
    data_dir = Path(__file__).resolve().parent.parent / "DATA"
    icd_path = data_dir / "ICD-diagnoses.txt"
    ops_path = data_dir / "OPS-procedures.txt"

    if not icd_path.exists():
        print(f"ICD file not found: {icd_path}")
        sys.exit(1)
    if not ops_path.exists():
        print(f"OPS file not found: {ops_path}")
        sys.exit(1)

    try:
        import psycopg2
        conn = psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        print(f"Database connection failed: {e}")
        sys.exit(1)

    try:
        print("Ingesting ICD...")
        n_icd = ingest_icd_to_db(icd_path, conn)
        conn.commit()
        print(f"  ICD: {n_icd} rows")

        print("Ingesting OPS...")
        n_ops = ingest_ops_to_db(ops_path, conn)
        conn.commit()
        print(f"  OPS: {n_ops} rows")

        print("Done.")
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
