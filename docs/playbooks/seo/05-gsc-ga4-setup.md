# GSC + GA4 Service Account Setup

One-time setup for the measurement layer. ~15 minutes if you've used Google Cloud before; 30 minutes the first time.

## Prerequisites

- Owner-level access to the Google Search Console property for `draftandarc.com`.
- Edit-level access to the GA4 property for `draftandarc.com`.
- A Google account that can create a new Google Cloud project.

## Step-by-step

### 1. Create a Google Cloud project

1. Go to `console.cloud.google.com`.
2. Click the project dropdown (top left) → "New Project".
3. Name it `draftandarc-seo-measurement`. Leave organization blank if you don't have one.
4. Click "Create" and wait ~30 seconds.

### 2. Enable the two APIs

In the new project, go to "APIs & Services" → "Library".

1. Search for "Google Search Console API". Click it. Click "Enable".
2. Search for "Google Analytics Data API". Click it. Click "Enable".

(You do NOT need the Google Analytics Admin API — we deliberately avoided that dependency.)

### 3. Create a service account

1. Go to "IAM & Admin" → "Service Accounts" → "Create Service Account".
2. Name: `seo-measurement`. The email auto-fills as `seo-measurement@draftandarc-seo-measurement.iam.gserviceaccount.com`.
3. Skip the "grant access to project" step (we grant access *to GSC/GA4*, not to the GCP project).
4. Click "Done".
5. On the service account list, click the new account → "Keys" tab → "Add Key" → "Create new key" → "JSON".
6. The browser downloads `draftandarc-seo-measurement-XXXXX.json`. Move it to `~/.config/draftandarc/gcp-service-account.json`:
   ```bash
   mkdir -p ~/.config/draftandarc
   mv ~/Downloads/draftandarc-seo-measurement-*.json ~/.config/draftandarc/gcp-service-account.json
   ```

### 4. Grant the service account access to Search Console

1. Go to `search.google.com/search-console`.
2. Open settings (gear icon, bottom left) → "Users and permissions".
3. Click "Add user".
4. User email: the service account email from step 3 (`seo-measurement@draftandarc-seo-measurement.iam.gserviceaccount.com`).
5. Permission: **Restricted**. (Don't grant Full — least privilege. If `--mode validate` later returns a permission error from GSC, come back and upgrade to Full as the recovery step.)
6. Click "Add".

### 5. Grant the service account access to GA4

1. Go to `analytics.google.com`.
2. Bottom-left gear icon (admin).
3. In the "Property" column, click "Property access management".
4. Click "+" → "Add users".
5. Email: same service account email.
6. Role: **Viewer**.
7. Click "Add".

### 6. Note the GA4 property ID

Still in GA4 → Admin → Property settings → "Property details" → "PROPERTY ID" is a 9-or-10-digit number (e.g., `123456789`).

### 7. Populate `.env`

```dotenv
GOOGLE_APPLICATION_CREDENTIALS=/Users/<you>/.config/draftandarc/gcp-service-account.json
GSC_SITE_URL=sc-domain:draftandarc.com
GA4_PROPERTY_ID=123456789
```

### 8. Validate

```bash
uv run python main.py --mode validate
```

Expected: three `[PASS]` lines, one per integration. If any FAILs, re-check the corresponding grant step.

## Recovery: "I lost my service account JSON"

The JSON is a private key — Google won't regenerate the same one. To recover:

1. Go to GCP → IAM & Admin → Service Accounts → the service account → Keys.
2. Create a new key (same flow as step 3.5 above). Save to the same path.
3. The old key remains valid until you delete it; delete it from the Keys list to be safe.

No re-grants needed in GSC or GA4 — the service account email didn't change.

---
Last updated: 2026-05-26
