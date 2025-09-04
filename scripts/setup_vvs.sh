#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   PROJECT_ID=your-proj LOCATION=us-central1 bash scripts/setup_vvs.sh
# Optional:
#   BUCKET=gs://your-bucket   (for future batch ops; not required)

: "${PROJECT_ID:?Set PROJECT_ID}"
LOCATION="${LOCATION:-us-central1}"
BUCKET="${BUCKET:-}"

echo "==> Using PROJECT_ID=$PROJECT_ID LOCATION=$LOCATION"

# Enable required services
gcloud config set project "$PROJECT_ID" 1>/dev/null
gcloud services enable aiplatform.googleapis.com storage.googleapis.com --project "$PROJECT_ID"

# Optional bucket
if [[ -n "${BUCKET}" ]]; then
  if ! gcloud storage buckets describe "${BUCKET}" --project "$PROJECT_ID" >/dev/null 2>&1; then
    echo "==> Creating bucket ${BUCKET}"
    gcloud storage buckets create "${BUCKET}" --location="${LOCATION}" --project "$PROJECT_ID"
  else
    echo "==> Bucket ${BUCKET} exists"
  fi
fi

# Ensure venv and deps
PY=python3
if ! command -v ${PY} >/dev/null; then PY=python; fi
${PY} -m venv .venv_vvs
source .venv_vvs/bin/activate
pip -q install --upgrade pip
pip -q install google-cloud-aiplatform

# Provision index + endpoint via SDK
export PROJECT_ID LOCATION
${PY} scripts/provision_vvs.py

# Expect the script to emit INDEX/ENDPOINT lines; capture last ones
INDEX=$(grep -E "^INDEX:" scripts/.provision.log 2>/dev/null | tail -n1 | sed 's/^INDEX:\s*//')
ENDPOINT=$(grep -E "^ENDPOINT:" scripts/.provision.log 2>/dev/null | tail -n1 | sed 's/^ENDPOINT:\s*//')

if [[ -z "${INDEX}" || -z "${ENDPOINT}" ]]; then
  echo "ERROR: Could not parse INDEX/ENDPOINT from scripts/.provision.log"
  exit 1
fi

# Write env file for the app
cat > .env.vvs <<EOF
GOOGLE_CLOUD_PROJECT=${PROJECT_ID}
GOOGLE_CLOUD_LOCATION=${LOCATION}
VVS_INDEX=${INDEX}
VVS_ENDPOINT=${ENDPOINT}
VVS_ENABLED=true
VVS_NAMESPACE_MODE=session
EOF

echo "==> Wrote .env.vvs with VVS settings"
echo "==> Done. First deploy may take ~20–30 minutes. You can re-run smoke test later."