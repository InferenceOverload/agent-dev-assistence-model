#!/usr/bin/env bash
set -euo pipefail
schema="$1"
file="$2"
python3 - "$schema" "$file" <<'PY'
import json, sys
schema_path, file_path = sys.argv[1], sys.argv[2]
schema = json.load(open(schema_path))
data = json.load(open(file_path))
missing = [k for k in schema.get("required", []) if k not in data]
if missing:
    raise SystemExit(f"[INVALID] Missing keys: {missing}")
print("[OK] JSON required keys present")
PY