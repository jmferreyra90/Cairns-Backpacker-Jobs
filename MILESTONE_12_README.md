# Cairns Backpacker Jobs — Milestone 12

## First real *self-addressed* email, from a saved draft and private dummy CV

**Scope:** owner-only, password-protected Render staging. **No employer emails**, no mass sending, no new public sign-up workflow. The `ENABLE_REAL_SEND=false` guard for employer campaigns stays unchanged. This milestone uses a separate, explicit self-test permission.

This package is an **incremental patch on Milestone 11**. It does not contain a whole independent project. It deliberately **does not include `app/services/account_auth.py`**, so the Supabase magic-link redirect correction you made in Milestone 10 remains in place.

## What works

1. Log in with your verified Supabase email, create/open a saved draft and upload a **fictional** PDF/DOCX in the private `cv-test-private` bucket.
2. Open the **Milestone 12 — email a tu propia cuenta** link from your draft.
3. Review the exact self-addressed subject and personalised cover letter.
4. Connect Gmail with Google OAuth (`gmail.send`); optionally connect **personal** Outlook with Microsoft OAuth (`Mail.Send`). The provider account email **must exactly match** the verified Supabase email and `SELF_TEST_OWNER_EMAIL`.
5. Check an explicit confirmation box and send **one** message containing the dummy CV **to that same email address**.
6. The attempt is saved before the provider call. **One attempt per draft**, even on HTTP errors, duplicate clicks, restarts or uncertain responses. A successful HTTP status means **accepted by provider, not delivered**. Check both Inbox and Sent.

No provider access/refresh tokens or CV bytes are saved in your application database or browser cookies. A short-lived access token is held in **server RAM only**; reconnect if Render restarts. The database stores attempt status, provider, recipient and time (no email body or attachment).

## Files in this patch

| Path | Action |
|---|---|
| `app/main.py` | Replace — feature flag / startup fail-closed checks |
| `app/routes/account_beta.py` | Replace — show the self-test link when the viewer is the allowed owner |
| `app/templates/account_draft.html` | Replace — add the self-test link |
| `app/services/private_cv.py` | Replace — add private Storage download; retains upload/remove |
| `app/models_selftest.py` | New — permanent one-attempt-per-draft constraint |
| `app/services/selftest_cache.py` | New — short-lived OAuth access token kept in server RAM |
| `app/services/selftest_send.py` | New — Gmail / Microsoft Graph provider calls |
| `app/routes/selftest.py` | New — OAuth, preview, explicit send, status |
| `app/templates/account_selftest.html` | New — Spanish UI |
| `.env.m12.example` | Reference only — **do not replace `.env`** |
| `tests/test_m12_safety.py` | New — offline unit tests |

> If you have made edits to any existing files since Milestone 11, compare/merge rather than blindly overwriting them. **Especially preserve your corrected `account_auth.py`.**

## Step 1 — Back up your working Milestone 11

Open **VS Code -> Terminal -> New Terminal** in the existing project directory.

```powershell
git status
git add .
git commit -m "Complete milestone 11"
```

If Git says nothing to commit, continue. Do not add `.env`, API secrets, your SQLite database or real CVs.

Extract the Milestone 12 ZIP to a separate folder, then copy its files into the corresponding paths in your existing project. Merge folders; **do not delete existing folders**.

The Python dependencies already used by earlier milestones should suffice (FastAPI, SQLAlchemy, `authlib`, `httpx`, Supabase Python, psycopg and Jinja2). Ensure `requirements.txt` includes `authlib`, `httpx`, `supabase` (from previous milestones). This patch adds no new library.

## Step 2 — Configure Google OAuth (recommended first)

Go to [Google Cloud Console](https://console.cloud.google.com/) and select the Google Cloud project where you registered your app. Enable **Gmail API** for that project if it is not enabled. Set up **Google Auth Platform -> Audience** as *External / Testing* and add the **same email you use for Supabase sign-in** to the Test users list. Use the least-privilege `https://www.googleapis.com/auth/gmail.send` scope (plus OpenID/email). Google may display an *unverified app* notice during testing.

Under **Clients / Credentials**, create or reuse a **Web application** OAuth client, and add the exact *Authorized redirect URI*:

```
https://cairns-backpacker-jobs.onrender.com/cuenta/prueba/callback/google
```

Replace the host with **your actual Render host** if different. This is a **new** callback, distinct from the old local `/auth/google/callback` and from Supabase Auth `/cuenta/callback`. You may retain other valid redirect URIs for local work.

Copy Client ID and Secret into Render Environment (not GitHub). If your Gmail is not the same as your verified Supabase email, this beta deliberately refuses to connect it.

### Optional: personal Microsoft Outlook

If your Microsoft app is already configured, add this redirect URI in Microsoft Entra App registrations -> Authentication -> Web:

```
https://cairns-backpacker-jobs.onrender.com/cuenta/prueba/callback/microsoft
```

Keep the Microsoft delegated scopes `Mail.Send` and `User.Read` and the application permission model needed for your test account. **Our existing OAuth client points to the `/consumers` authority**; use a *personal* Outlook/Hotmail account, not JCU organisational credentials, for this test. Gmail is the recommended first test.

## Step 3 — Render environment variables

Render -> Your Web Service -> **Environment**. Keep all working Milestone 10/11 settings. In particular, preserve `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`, `APP_SESSION_SECRET`, `APP_PUBLIC_URL`, `STAGING_USERNAME`, `STAGING_PASSWORD`, and `CV_CLEANUP_TOKEN`.

Add:

```dotenv
STAGING_ENABLE_SELF_TEST=true
SELF_TEST_OWNER_EMAIL=your_same_verified_email@example.com
GOOGLE_CLIENT_ID=your_google_oauth_web_client_id
GOOGLE_CLIENT_SECRET=your_google_oauth_web_client_secret
```

Ensure these remain:

```dotenv
APP_MODE=staging
STAGING_ENABLE_ACCOUNTS=true
STAGING_ENABLE_FORMS=true
STAGING_ENABLE_DRAFT_FILES=true
ENABLE_REAL_SEND=false
ENABLE_LOCAL_ADMIN=false
```

**Do not set `ENABLE_REAL_SEND=true`.** This is NOT required for your one-address test; it would break the staging safety checks.

`SELF_TEST_OWNER_EMAIL` must exactly match your verified Supabase email (case insensitive). Only that user sees/uses the test flow. Do not use an arbitrary or third-party email.

### Database migration

At startup the app already calls `Base.metadata.create_all()`; the new `app_private.self_test_attempts` table is created when the flag is enabled. That assumes your existing Supabase database user has `CREATE TABLE` rights in the private `app_private` schema, as in Milestones 10–11. **No data reset or Supabase bucket recreation needed.**

## Step 4 — Commit and deploy

```powershell
git status
git add .
git commit -m "Milestone 12: one-address email self-test"
git push
```

Wait for Render to show **Live**. Confirm the startup log contains no missing-env-variable or database permission errors.

## Step 5 — End-to-end test

1. Open the hosted site, enter the **staging Basic Auth** password, and sign in to **Mi cuenta** with your verified Supabase magic link.
2. Open an existing saved draft (or make a new one with 1–10 sample businesses). Upload a **fictional PDF <1MB** if necessary. **Don't upload a real person's CV yet.**
3. Click **Milestone 12 — email a tu propia cuenta**.
4. Verify the intended recipient is **your verified email**, and review the subject/body.
5. Click **Conectar Gmail**, select your exact same email, approve Google OAuth. The app redirects back to the review page.
6. Tick the explicit confirmation and click **Enviar un email de prueba a mí mismo** **once**.
7. Check the status. **Accepted** means the API accepted the request, not that an email definitely arrived. Check **Gmail Sent** and **Inbox**. If it says **uncertain**, check Sent before doing anything else. Do **not** retry the same request automatically.
8. Reload the page and verify the attempt remains recorded and the send button is gone. Opening the same draft in another tab does not allow a second send. No businesses should receive email.

**If you need another self-test:** create a *new* dummy draft. Be cautious about provider test quotas/rate limits. Never resend an uncertain attempt until you have checked Sent carefully.

## Disable instantly

Change this Render variable and redeploy:

```dotenv
STAGING_ENABLE_SELF_TEST=false
```

This removes the hosted self-test routes. Your existing read-only preview, draft accounts and simulated queue remain enabled.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Render startup fails | `SELF_TEST_OWNER_EMAIL`, `STAGING_ENABLE_*`, Gmail/Microsoft OAuth ID and secret, DB table permission |
| Google `redirect_uri_mismatch` | Google Web OAuth client redirect URI must be exact, including host, https and `/cuenta/prueba/callback/google` |
| Google says app not verified / access blocked | Add your test Gmail to Google Auth Platform -> Audience -> Test users and enable Gmail API |
| Redirect returns to login | Sign in using Supabase in the same browser; remember Google OAuth is separate from Supabase Auth |
| Email mismatch | Your Supabase-verified email, `SELF_TEST_OWNER_EMAIL`, and connected Gmail/Outlook mailbox must all match |
| Says reconnect | Render restarted or OAuth token expired; connect Gmail again (if no test attempt yet) |
| HTTP 401/403 rejected | Provider OAuth consent, scopes, expired token, test users, or incorrect credentials |
| Status uncertain | Network error, provider 5xx/429, or interrupted send. Check Sent; no automatic retry |
| CV unavailable | 24-hour expiry, deletion, bad file, private bucket configuration |
| Outlook rejected for size | For Outlook use a dummy CV smaller than 2.5 MB |

Never post any bearer tokens, magic links, OAuth callback URLs containing `code`, Render secrets or real CVs to support logs.

## Local offline safety tests

With the project virtual environment activated and dependencies installed:

```powershell
python -m pytest -q tests/test_m12_safety.py
```

Tests validate that both provider APIs address mail to the connected account and that PostgreSQL's intended unique constraint concept rejects duplicate per-draft attempts (using SQLite for the isolated test). The tests mock network calls and do **not** send actual messages. Live OAuth and delivery still need an explicit owner-only test on Render.

## Why not real employer sending yet?

The `app_private.draft_simulations` queue remains a **simulation only**. Sending to multiple employers requires a reviewed recipient directory, explicit per-recipient confirmation, permission/abuse controls, an idempotent worker strategy, handling provider throttling, verified privacy/deletion flows, and production-grade infrastructure. Gmail's `gmail.send` scope is sensitive and its public distribution may require additional Google verification. This milestone is a real **single self-addressed** provider test—not an authorisation for public mass-email sending.
