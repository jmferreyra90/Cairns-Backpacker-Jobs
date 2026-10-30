# Milestone 8 — First hosted PRIVATE preview (Render + Supabase)

**This ZIP is an overlay for Milestone 7, not a new project. It is deliberately NOT a public release for real jobseekers.**

## Goal and safety boundary

- Keep local Milestones 1–7 working under `APP_MODE=local` (the default).
- Host a **private, password-protected directory-only preview** under `APP_MODE=staging`.
- Hosted staging exposes only `/`, static assets, and `/health`. No CV uploads, applicant contact forms, Gmail/Outlook callbacks, employer sending, campaign history, `/docs`, or local admin routes are registered.
- It only displays business name, category and address (no manager names/emails or applicant data).
- Transfer **only** public business seed data to hosted Supabase, not local SQLite files, applicant contacts, CVs, access tokens or prior campaigns.
- Free tiers are for development: Render free web apps sleep after 15 minutes and lose local files on restart. Supabase free databases may pause due to inactivity. Google Gmail OAuth review and robust hosting, privacy, and sending safeguards are still unfinished.

## 1. Copy files into your existing project

Commit/back up your project first (from the project root):

```powershell
git status
git add .
git commit -m "Back up milestone 7 before staging deployment"
```

**Replace:**

- `app/main.py`
- `app/database.py`
- `app/routes/businesses.py`

**Add:**

- `app/middleware/__init__.py`
- `app/middleware/staging_gate.py`
- `app/templates/staging_directory.html`
- `app/import_staging_directory.py`
- `requirements-additions.txt`
- `.env.staging.example`
- `MILESTONE_8_README.md`

**Preserve:** `data/cairns_jobs.db`, `data/businesses.csv`, your `.env`, all remaining routes, services, models, templates, and existing `requirements.txt`.

The new `app/database.py` uses SQLite by default, exactly as before, but accepts an explicit `DATABASE_URL` for PostgreSQL. The default local DB path is unchanged.

## 2. Install the additional PostgreSQL driver

In VS Code PowerShell, activate `venv` or `.venv` and execute:

```powershell
python -m pip install -r requirements-additions.txt
python -m pip freeze > requirements.txt
```

New tool: **psycopg 3** is the PostgreSQL database driver that SQLAlchemy uses to connect Python to Supabase.

## 3. Verify your existing local app

In your existing `.env`, **do not set `DATABASE_URL`** unless you deliberately intend to change the local database. Leave `APP_MODE` absent or set `APP_MODE=local`. Keep your current app session secret and other values.

```powershell
python -m uvicorn app.main:app --reload --host localhost
```

- `http://localhost:8000/` should display the original selectable business list.
- `http://localhost:8000/admin/businesses` should still work with the local-only admin settings from Milestone 7.
- Stop with Ctrl+C before proceeding.

## 4. Set up the free hosted PostgreSQL database

1. Create/sign in at https://supabase.com/dashboard. Create a **Free** project for Cairns Backpacker Jobs. Select a region reasonably close to Australia if offered.
2. Save the database password in a password manager. Don't place it in chat, screenshots, source control or public documents.
3. Click **Connect** in the Supabase project and copy the **Session pooler** connection string (usually port `5432`; important for IPv4 support). **Do not invent the pooler hostname.**
4. Convert the initial prefix from `postgresql://` to `postgresql+psycopg://` if necessary. Add `?sslmode=require` if not already present. If your password contains `@`, `#`, `%`, `:`, `/` or other special URI characters, percent-encode it for the connection URL; alternatively create a URI-safe strong password.
5. Create a local file named `.env.staging` (from `.env.staging.example`) with:

```dotenv
APP_MODE=staging
DATABASE_URL=postgresql+psycopg://postgres.YOUR_PROJECT:URL_ENCODED_PASSWORD@YOUR_POOLER_HOST:5432/postgres?sslmode=require
```

Replace the placeholders using the actual Supabase **Connect** panel. This file is private and must be gitignored. A direct database endpoint often requires IPv6; use the session pooler when connecting from an IPv4-only environment.

## 5. Import ONLY the business seed

**Check your `.gitignore` before proceeding:**

```gitignore
.env
.env.*
!.env.example
!.env.staging.example
venv/
.venv/
__pycache__/
*.db
```

Do not delete existing rules. Check no secrets or databases are tracked:

```powershell
git check-ignore -v .env .env.staging data/cairns_jobs.db
```

If any of these files are tracked, stop and remove them from Git's index without deleting the files (example: `git rm --cached .env.staging`). Investigate any accidentally exposed credentials and rotate them.

The new importer reads `.env.staging` *before* importing the database module, so it cannot silently use your local SQLite database. From the project root run:

```powershell
python -m app.import_staging_directory data/cairns_businesses_seed.csv
```

Dry-run output: `DRY RUN: N new, M existing/duplicate`. Apply only when correct:

```powershell
python -m app.import_staging_directory data/cairns_businesses_seed.csv --apply
```

**This does NOT migrate your full local database.** It only imports the business CSV as unverified public directory entries. Do not copy `cairns_jobs.db` to Supabase or upload applicant data into staging.

If the connection fails, check that your project's Supabase database is active, the pooler URL is correct, the port is `5432`, SSL is enabled, and the password is percent-encoded where required.

## 6. Check the local staging preview before deployment

Optionally create a *second terminal* and set temporary environment variables in that PowerShell process. For quick testing you may use your existing local SQLite database; **do not** set your hosted DATABASE_URL here. Example:

```powershell
$env:APP_MODE = 'staging'
$env:STAGING_USERNAME = 'owner'
$env:STAGING_PASSWORD = 'YOUR_24_PLUS_CHARACTER_RANDOM_PASSWORD'
python -m uvicorn app.main:app --reload --host localhost
```

Open `http://localhost:8000/` and enter these staging credentials; only business names, categories, addresses and filters should appear. The URL `/admin/businesses` and `/compose` must return 404 after authentication. `/health` should return `{"status":"ok"}` without credentials.

After stopping the process, clear these temporary settings **in the same terminal** before resuming normal local development:

```powershell
Remove-Item Env:APP_MODE
Remove-Item Env:STAGING_USERNAME
Remove-Item Env:STAGING_PASSWORD
```

If a staging `DATABASE_URL` is already set in the PowerShell process, remove that too (`Remove-Item Env:DATABASE_URL`).

## 7. Put the code on GitHub

Make a **private** GitHub repository, e.g. `cairns-backpacker-jobs`. It can still be connected to Render. Check `git status` and `git ls-files` for accidental private files **before pushing**.

```powershell
git add .
git commit -m "Add private hosted staging preview"
git branch -M main
git remote -v
```

If the repository has **no** `origin` yet:

```powershell
git remote add origin https://github.com/YOUR_USERNAME/cairns-backpacker-jobs.git
git push -u origin main
```

If `origin` already exists, simply `git push` (or `git push -u origin main` if the branch isn't tracked). Create the empty GitHub repository first; do not initialise with an extra README if your local repository already has history.

## 8. Deploy to Render Free

Visit https://dashboard.render.com and select **New → Web Service**. Connect your **private** GitHub repo. Configure:

| Render setting | Value |
|---|---|
| Runtime | Python 3 |
| Instance type | **Free** |
| Root directory | Repository root (leave blank) |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/health` |

Add **Environment Variables** in the Render dashboard. Do **not** upload your local `.env`, since it may contain Gmail and Microsoft secrets that this preview does not need.

```dotenv
APP_MODE=staging
ENABLE_REAL_SEND=false
ENABLE_LOCAL_ADMIN=false
STAGING_USERNAME=owner
STAGING_PASSWORD=REPLACE_WITH_LONG_RANDOM_PASSWORD
DATABASE_URL=postgresql+psycopg://...YOUR_REAL_SUPABASE_SESSION_POOLER_URL...
PYTHON_VERSION=3.12.10
```

`STAGING_PASSWORD` must contain at least **24 characters**. Generate a password locally:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Paste the actual value into Render's Environment Variables only. `APP_SESSION_SECRET`, Google IDs and Microsoft IDs are **not needed** on the staging web service. Don't enable real sending on this service.

Render automatically sets `RENDER=true`. The new app **refuses to start on Render unless `APP_MODE=staging` and a PostgreSQL `DATABASE_URL` are configured**. It also does not register any form, auth, admin or campaign endpoints in staging.

Click **Deploy Web Service**. After successful deployment, Render shows an HTTPS `https://YOUR-SERVICE.onrender.com` address. Visit it and enter your staging credentials in your browser's password dialog. The app should show the read-only directory. `/health` shows `{"status":"ok"}` without credentials.

## 9. Staging verification

1. Test the production HTTPS URL in a private/incognito browser; without the password it should return 401.
2. After logging in, verify 14 starter businesses appear if the import succeeded, and search/category filters work.
3. `/compose`, `/connect/google`, `/connect/microsoft`, `/admin/businesses`, `/campaigns/start`, and `/docs` must not be available (404 **after** passing the preview password gate).
4. Do not submit CVs or collect contact details in staging; those functions are unavailable.
5. After the web service has been idle for 15 minutes, the next visit may take about a minute to wake it up.
6. Confirm Supabase table `businesses` contains public seed data; `applicant_contacts` and `campaigns` must remain empty.
7. Stop: if the site exposes any user details, credentials, CV uploads or email-sending controls, disable the Render service and investigate before sharing the link.

## 10. Not ready for public launch yet

**Milestone 8 is a private preview, not a production launch.** Before offering the actual app to backpackers, plan for:

- Proper user accounts and authenticated history (current app uses browser sessions).
- A secure user-facing admin account instead of localhost-only Basic auth.
- Durable encrypted temporary CV/object storage with expiry, malware/attachment scanning, retention controls.
- Durable sending worker/queue with idempotency across restarts; more robust abuse and rate limits.
- Server-side secure OAuth storage, correct production redirect URIs, and provider verification (including Google `gmail.send` sensitive scope).
- A final privacy policy with real controller/contact, data retention, hosting location and deletion/export processes, and an unsubscribe system for optional marketing/feedback emails.
- Business contact review, recruitment-specific recipient suitability, regulatory/legal review and actual live-delivery testing.
- Database backups, recovery plan, logging redaction and monitoring.
- Upgrade the hosting tiers if people start relying on the service; free tiers aren't a production availability guarantee.

This is intentionally a deployable, reversible checkpoint: local features stay intact, the hosted preview remains safe to inspect, and no credentials or personal data are uploaded to GitHub.
