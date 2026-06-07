#!/usr/bin/env bash
# Re-runnable Application Default Credentials login with the scopes our
# Python clients need (GSC + GA4 readonly).
#
# Google's default gcloud client ID blocks analytics.readonly and
# webmasters.readonly — you must use your own OAuth client ID.
#
# One-time prerequisite:
#   1. GCP console → project draftandarc-seo-measurement
#   2. APIs & Services → Credentials → Create Credentials → OAuth client ID
#   3. Application type: Desktop app  |  Name: seo-measurement-cli
#   4. Download JSON → save to ~/.config/draftandarc/oauth-client.json
#      mkdir -p ~/.config/draftandarc && mv ~/Downloads/client_secret_*.json ~/.config/draftandarc/oauth-client.json
#
# Usage:
#   bash scripts/gcloud-adc-login.sh

set -euo pipefail

CLIENT_ID_FILE="${HOME}/.config/draftandarc/oauth-client.json"

if [[ ! -f "$CLIENT_ID_FILE" ]]; then
  echo "ERROR: OAuth client file not found at $CLIENT_ID_FILE"
  echo
  echo "Create it first:"
  echo "  1. GCP console → project draftandarc-seo-measurement"
  echo "  2. APIs & Services → Credentials → Create Credentials → OAuth client ID"
  echo "  3. Application type: Desktop app  |  Name: seo-measurement-cli"
  echo "  4. Download JSON → save to $CLIENT_ID_FILE:"
  echo "     mkdir -p ~/.config/draftandarc && mv ~/Downloads/client_secret_*.json $CLIENT_ID_FILE"
  exit 1
fi

SCOPES=(
  "openid"
  "https://www.googleapis.com/auth/userinfo.email"
  "https://www.googleapis.com/auth/cloud-platform"
  "https://www.googleapis.com/auth/webmasters.readonly"
  "https://www.googleapis.com/auth/analytics.readonly"
)

SCOPES_CSV=$(IFS=, ; echo "${SCOPES[*]}")

echo "Using OAuth client: $CLIENT_ID_FILE"
echo "Opening browser for ADC login with scopes:"
for s in "${SCOPES[@]}"; do echo "  - $s"; done
echo

gcloud auth application-default login \
  --client-id-file="$CLIENT_ID_FILE" \
  --scopes="$SCOPES_CSV"

echo
echo "Credentials saved. Verify with:"
echo "  cat ~/.config/gcloud/application_default_credentials.json | head -5"
echo
echo "Then re-run: make validate"
