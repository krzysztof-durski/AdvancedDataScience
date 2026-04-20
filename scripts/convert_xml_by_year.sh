#!/bin/bash
# Convert XML to JSON in batches — one command per year.
# Run all: ./scripts/convert_xml_by_year.sh
# Run one: python scripts/xml_to_json.py --year 2024

YEARS=(2008 2010 2012 2013 2014 2015 2016 2018 2020 2021 2022 2023 2024)

cd "$(dirname "$0")/.." || exit 1

if [[ -n "$1" ]]; then
  # Single year: ./scripts/convert_xml_by_year.sh 2024
  python3 scripts/xml_to_json.py --year "$1"
else
  for year in "${YEARS[@]}"; do
    echo "=== Year $year ==="
    python3 scripts/xml_to_json.py --year "$year"
    echo ""
  done
fi
