# Milestone 11 — Private **dummy** CV storage + persistent simulation queue

This is an overlay patch for the project at Milestone 10. It is **NOT a complete standalone project** and **does not send any email**. The signed-in user must still be inside the password-protected staging environment.

**Important:** This remains an owner-only beta. Do **not** upload real resumes, launch to backpackers, or set `ENABLE_REAL_SEND=true`. PDF/DOCX structural checks are not antivirus or malware scanning; provider approval, file retention reliability, and public privacy compliance remain future work.

## 0. Before you copy

- Confirm that the Milestone 10 magic-link callback and `/cuenta` profile currently work.
- `git status` to examine changes. Save a commit, or back up customised files.
- Leave the **magic link correction in `app/services/account_auth.py`** intact. This ZIP does **not** replace it.
- Never replace `.env`, the existing database, `models_accounts.py` or your Supabase project.

## 1. Files

| File | Action |
|---|---|
| `app/main.py` | Replace |
| `app/middleware/staging_gate.py` | Replace (allows token-secured cleanup path to bypass Basic Auth; all other pages remain protected) |
| `app/routes/account_beta.py` | Replace |
| `app/routes/draft_ops.py` | **New** |
| `app/models_draft_ops.py` | **New** |
| `app/services/private_cv.py` | **New** |
| `app/templates/account_draft.html` | Replace |
| `app/templates/account_home.html` | Replace |
| `app/templates/account_simulation.html` | **New** |
| `app/templates/privacy.html` | Replace draft text; complete legal placeholders before public use |
| `.github/workflows/cv-cleanup.yml` | **New** scheduled cleanup job |
| `.env.m11.example` | **New** reference only |
| `requirements-additions.txt` | Contains one new package (`supabase`); use it to install, then freeze `requirements.txt` |

The `app_private` schema is created in Milestone 10. The three new tables are `app_private.draft_cvs`, `app_private.draft_simulations`, `app_private.draft_simulation_items` via `Base.metadata.create_all`. Existing records are not overwritten.

## 2. Install Python dependency

From VS Code / PowerShell in the project root:

```powershell
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements-additions.txt
python -m pip freeze > requirements.txt
```

If your virtual environment is named `.venv`, adjust the activation path accordingly.

## 3. Create a private Supabase Storage bucket

Supabase Dashboard -> **Storage** -> **New bucket**:

- Bucket name: **`cv-test-private`** (must match exactly)
- **Private** (turn Public **off**)
- Restrict file size to **5 MB**
- Allowed content types: `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`

For this specific beta, **do not create public Storage access policies**. The *trusted server* accesses this bucket using a secret key, after authenticating and authorising the current owner. No browser receives Storage credentials, a public URL or a signed download link. This is an elevated server key: protect it carefully and do not log it.

Supabase Dashboard -> Project Settings -> **API Keys** -> **Secret keys**: copy an `sb_secret_...` key. This is **not** the earlier publishable key, database password, or service URL.

## 4. Set Render environment variables

Render -> your Web Service -> **Environment**: add:

```dotenv
STAGING_ENABLE_DRAFT_FILES=true
SUPABASE_SECRET_KEY=sb_secret_YOUR_REAL_SECRET
CV_CLEANUP_TOKEN=YOUR_RANDOM_TOKEN
```

**Keep** these already-configured values:

```dotenv
APP_MODE=staging
STAGING_ENABLE_ACCOUNTS=true
STAGING_ENABLE_FORMS=true
ENABLE_REAL_SEND=false
ENABLE_LOCAL_ADMIN=false
```

Keep also `DATABASE_URL`, `APP_PUBLIC_URL`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `APP_SESSION_SECRET`, `STAGING_USERNAME`, `STAGING_PASSWORD`.

Generate `CV_CLEANUP_TOKEN` in PowerShell (not your key, not the app session secret):

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Save, rebuild, deploy. **Never put the secret key or cleanup token in `.env.example`, Git, HTML or logs.**

## 5. Configure scheduled cleanup on GitHub

CVs become unusable after 24 hours based on their saved expiry timestamp. **Physical deletion is not guaranteed at 24 hours**: it occurs when the authenticated cleanup task runs successfully. Render Free can sleep and does not provide a continuously running worker.

In your GitHub repository go to **Settings -> Secrets and variables -> Actions -> New repository secret**, and add:

| Secret name | Value |
|---|---|
| `RENDER_STAGING_URL` | Your full HTTPS Render origin, e.g. `https://your-app.onrender.com` (no trailing path) |
| `CV_CLEANUP_TOKEN` | **Exact same** random cleanup token set in Render |

Make sure GitHub Actions are enabled and the `.github/workflows/cv-cleanup.yml` file has been pushed to your default branch. GitHub Actions -> **Expire dummy CV files** -> **Run workflow** is a useful manual test. It is scheduled once daily, generally around **03:23 UTC**; scheduled jobs can be delayed or skipped. Check the workflow log. A `200` response with `{"removed":N}` indicates it ran; `401` means the token is missing or mismatched. A free service wake-up can delay it.

**If you don't enable this workflow, do not assume expired objects will automatically disappear.** You can leave `STAGING_ENABLE_DRAFT_FILES=false` until cleanup works.

## 6. Push code

```powershell
git status
# Review carefully — .env, *.db, personal files and tokens MUST NOT be included.
git add .
git commit -m "Milestone 11: private dummy CVs and persistent simulation queue"
git push
```

Check Render -> Logs and Events for successful startup. If startup fails because `SUPABASE_SECRET_KEY` or `CV_CLEANUP_TOKEN` is missing, fix Render settings rather than turning off safety checks.

## 7. Test in hosted staging

1. Open your Render URL; enter the **staging password**.
2. Open **Mi cuenta**, sign in with a *fresh* Supabase magic link if needed.
3. Save your profile and create a saved draft with two fictional/test business entries.
4. Open the saved draft: a new **CV de prueba (privado)** section should appear.
5. Upload a **dummy** PDF or DOCX no larger than 5 MB; tick the checkbox confirming it contains no real data.
6. Return to the draft; you should see the filename and an **Eliminar CV de prueba** action.
7. Click **Iniciar simulación (no envía emails)**. The progress page should show one business change to **Simulado** at a time.
8. Reload the page, or close the tab and return. It should **resume from PostgreSQL**, without duplicating completed items. Processing requires the progress page to be open: no always-on worker is running.
9. Delete the CV or draft and verify its removal from Supabase Storage. For expiry, use GitHub Actions **Run workflow** and inspect the output after the file actually expires.
10. Ensure `/connect/google`, `/connect/microsoft`, `/campaigns`, `/admin/businesses` remain unavailable on the hosted site. Confirm `ENABLE_REAL_SEND=false`.

## 8. Troubleshooting

- **File upload error:** Check the bucket exists, is private, and has the exact name `cv-test-private`; check `SUPABASE_SECRET_KEY` is a real `sb_secret_` key with server-side access; check the MIME and size restrictions.
- **No CV section:** `STAGING_ENABLE_DRAFT_FILES` not set to `true`, or updated code not deployed.
- **HTTP 403:** Expired/incorrect CSRF; refresh draft page. Use the same browser for magic-link login.
- **HTTP 404 on another draft:** Expected owner-only access control.
- **Cleanup 401:** GitHub and Render `CV_CLEANUP_TOKEN` values mismatch.
- **Queue stops on Render sleep:** Reopen `/cuenta`, select the saved draft and **Ver progreso**. Its state remains in PostgreSQL. The browser triggers only simulated steps, *not email sends*.
- **Existing user login broken:** Do not overwrite your corrected `account_auth.py` with old Milestone 10 versions. Check `/cuenta/callback` and Render logs.

## 9. Architectural notes and limitations

- Objects use random storage keys under account/draft IDs. Supabase Storage is a **private bucket**, not a public URL; upload and removal are performed server-side.
- Metadata is in PostgreSQL (`app_private`) and includes the filename, size, owner-linked draft and expiry; no full CV bytes in the database.
- The draft owner is verified using their existing authenticated browser session before any file or simulation operation.
- One CV per draft; delete it before uploading a replacement. Only one simulation per draft prevents duplicates.
- The queue is database-backed, but **the browser drives simulation** via authenticated, CSRF-checked POST requests. A real asynchronous worker and real Gmail/Outlook sends will be separate later milestones.
- CV validation is structural only, not malware scanning. This is not suitable for accepting real resumes from backpackers yet.
- Manual delete attempts removal from Storage before removing metadata. Scheduled cleanup removes expired files and references in batches of 100. Failed removals retain the reference so cleanup can retry. A few edge cases (failed upload compensation, outages, backups) can still require an administrator to reconcile orphaned objects; retention isn't yet guaranteed.
- New server-only key has elevated privileges, so its compromise would be serious. Rotate promptly if exposed.
- Supabase Free currently has 1 GB Storage included; monitor it in Supabase Usage. Render Free has important downtime/ephemeral-filesystem restrictions.
