# Cairns Backpacker Jobs — Milestone 9A: Controlled online application demo

This ZIP is an **overlay for the Milestone 8 project**, not a complete standalone project.

## Scope

When hosted as `APP_MODE=staging` with `STAGING_ENABLE_FORMS=true`, you can:
- browse, filter and select up to **10 active, non-blocked** Cairns businesses;
- open `/compose?ids=...`, complete a form with **fictional** contact information and attach a **dummy** PDF/DOCX CV (up to 5 MB);
- review a personalised English subject and body for every selected business;
- keep the existing staging Basic authentication and private business directory.

**Not enabled online:** Gmail/Outlook OAuth, actual or simulated campaign queue, user account registration, marketing collection, admin editing, or real email delivery. The app does **not** save contact information, the CV or email drafts to the database or files, and the only signed-cookie value is a CSRF token. The uploaded file is processed transiently and closed after validation. The server/framework may use temporary OS storage while receiving a file; don't use real CVs in this demo.

The `STAGING_ENABLE_FORMS=false` setting leaves the previous read-only Milestone 8 staging directory as it was. Local mode remains unchanged.

## 1. Back up and install

In your existing project folder, with VS Code PowerShell:

```powershell
git status
git add .
git commit -m "Save milestone 8 before staging demo"
```

Extract this ZIP and copy its **contents** into the existing `cairns-backpacker-jobs/` project, preserving subdirectories.

| File | Action |
|---|---|
| `app/main.py` | **REPLACE** |
| `app/routes/businesses.py` | **REPLACE** |
| `app/routes/staging_apply.py` | **NEW** |
| `app/templates/staging_directory.html` | **REPLACE** |
| `app/templates/staging_compose.html` | **NEW** |
| `app/templates/staging_review.html` | **NEW** |
| `.env.staging.example` | **REPLACE example only**, not your real `.env` |
| `.gitignore.additions` | NEW example of ignore rules; copy relevant lines into `.gitignore` |
| `MILESTONE_9_README.md` | NEW |

**Never replace or upload** `.env`, `.env.staging`, `data/cairns_jobs.db`, `app/models.py`, `app/database.py`, `app/models_campaign.py`, or your actual business records.

## 2. Configure Render (Environment)

Keep existing `STAGING_USERNAME`, `STAGING_PASSWORD`, `DATABASE_URL` from Milestone 8. Set exactly:

```dotenv
APP_MODE=staging
STAGING_ENABLE_FORMS=true
ENABLE_REAL_SEND=false
ENABLE_LOCAL_ADMIN=false
APP_SESSION_SECRET=<new random 32+ character secret>
```

Generate `APP_SESSION_SECRET` locally and COPY THE OUTPUT to Render (do not print the secret in chats or commit it):

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

The existing `STAGING_PASSWORD` needs 24+ characters. Leave the hosted OAuth client secrets unset. Render should serve with HTTPS and `RENDER=true` (automatically supplied by Render).

**Do not change `APP_MODE` to `local` on Render.** A startup guard prevents this. **Do not set `ENABLE_REAL_SEND=true`.** With forms enabled, the application refuses to start if that flag is true.

## 3. Test locally (optional)

For a local staging-mode test, create `.env.staging` with an appropriate test database and copy settings from the example. Since `load_dotenv()` loads `.env` by default, the most reliable option is to set temporary PowerShell environment variables for this terminal:

```powershell
$env:APP_MODE="staging"
$env:STAGING_ENABLE_FORMS="true"
$env:STAGING_USERNAME="owner"
$env:STAGING_PASSWORD="a_long_random_password_over_24_characters"
$env:APP_SESSION_SECRET="another_long_random_secret_over_32_characters"
$env:ENABLE_REAL_SEND="false"
# Point DATABASE_URL to a disposable test database; do not use your live Supabase database.
python -m uvicorn app.main:app --reload --host localhost
```

Use a clean browser to avoid session confusion. After the test close the terminal or remove those `$env:` overrides before returning to `APP_MODE=local`.

## 4. Commit to GitHub and deploy

Verify no secrets or database are tracked:

```powershell
git status
git check-ignore -v .env .env.staging data/cairns_jobs.db
```

If the files are not ignored, update `.gitignore` first. Then:

```powershell
git add .
git commit -m "Milestone 9: enable safe staging application preview"
git push
```

Open Render > your Web Service > **Environment**, add/update the variables above. Choose **Save, rebuild, and deploy**. Confirm the new deployment is live.

## 5. Test using the hosted site

1. Open the Render URL in a private browser window. The **Basic Auth** prompt must appear.
2. Select 1–3 business checkboxes (businesses with no email can also be selected for this **demo only**).
3. Click **Continuar a prueba**.
4. Enter dummy name `Alex Smith`, email `alex@example.com`, phone `0400000000`.
5. Subject: `Job Application - [Business Name]`.
6. Letter: `I'm interested in joining the team at [Business Name].`.
7. Upload a dummy PDF or DOCX under 5 MB. Check the **fictional data** checkbox.
8. Click **Revisar emails simulados**. Navigate with **Anterior/Siguiente**.
9. Confirm that no emails were sent and no applicant contacts were saved.
10. Check `https://YOUR-RENDER-URL/connect/google`, `/connect/microsoft`, `/admin/businesses`, `/mis-postulaciones` and `/docs`: they must return 404, after staging authentication.

**Important:** `/health` is intentionally available without a password, for Render's health checks.

## 6. Roll back / disable the demo

Set `STAGING_ENABLE_FORMS=false` in Render and redeploy. The original read-only directory returns immediately, without needing to undo your commits. No applicant data is persisted in this milestone.

## 7. Why this is not the public launch

The staging password is shared and does not authenticate independent applicants. Basic Auth, transient CV validation and a single-process app are not enough for an open public launch. Before promoting this to real backpackers, add proper user accounts, data-retention and consent workflows, production upload security, rate limits, a persistent delivery queue and provider OAuth verification. Collecting applicant contacts for marketing will be implemented only after that lawful, consented workflow is in place.
