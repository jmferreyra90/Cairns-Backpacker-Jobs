# Cairns Backpacker Jobs — Milestone 10

**Owner-tested, authenticated accounts + saved text drafts; no emails or CV storage.**
This patch overlays a completed Milestone 9 project. Do **not** replace the SQLite database, existing `.env`, or business records. Back up and commit your code first.

## What is included

| File | Action |
| --- | --- |
| `app/main.py` | REPLACE |
| `app/routes/businesses.py` | REPLACE |
| `app/templates/staging_directory.html` | REPLACE |
| `app/models_accounts.py` | ADD |
| `app/routes/account_beta.py` | ADD |
| `app/services/account_auth.py` | ADD |
| `app/templates/account_*.html` | ADD (six new templates) |
| `.env.m10.example` | ADD, example only |
| `secure_public_tables.sql` | ADD, run manually in Supabase SQL Editor |
| `MILESTONE_10_README.md` | ADD |

## 1. Prerequisites

- The Milestone 9 staging Render app must already work with Supabase PostgreSQL.
- Keep `APP_MODE=staging` and `ENABLE_REAL_SEND=false`.
- You need `httpx` and `email-validator` (installed during prior milestones). If missing:
  `python -m pip install httpx email-validator` and `python -m pip freeze > requirements.txt`.
- This feature is for **your own team-authorised email address only**. Don't invite the public.

## 2. Supabase Auth setup

In Supabase Dashboard:

1. In **Project Settings / API Keys**, copy the **Project URL** (`https://<project>.supabase.co`) and a **publishable key** (`sb_publishable_...`) or legacy **anon** key. **Never use a service-role or secret key** for this feature.
2. Under **Authentication → Providers → Email**, keep email authentication enabled and email confirmation on.
3. Under **Authentication → URL Configuration**, set the Site URL to your Render URL, e.g. `https://cairns-backpacker-jobs.onrender.com`.
4. Add `https://cairns-backpacker-jobs.onrender.com/cuenta/callback?state=**` to the **Redirect URLs** allow list. Replace the service hostname with yours. The `**` is needed because our callback includes a random state query parameter. Test the URL allow list if Supabase changes its matcher.
5. Use an email address in your Supabase organization's **Team**. The default SMTP service permits only pre-authorised team addresses and is limited to about **2 emails per hour per project**. Don't test repeatedly or with arbitrary applicants. For public registration, you'll need custom SMTP and abuse protection.
6. New Supabase Free projects with its default SMTP cannot edit authentication email templates; the code deliberately uses the **default magic link**, not a six-digit OTP.

Useful current docs:
- https://supabase.com/docs/guides/auth/auth-smtp
- https://supabase.com/docs/guides/auth/auth-email-passwordless
- https://supabase.com/docs/guides/auth/redirect-urls
- https://supabase.com/changelog/46599-changes-to-email-template-customisation-on-free-tier

## 3. Supabase SQL safety check

Open **Supabase → SQL Editor**. Review and run `secure_public_tables.sql`.
It enables row-level security on existing `public.applicant_contacts`, `public.campaigns`, and `public.campaign_attempts` if present, without adding public policies. It does not alter business listings. 

New records will be stored in PostgreSQL schema `app_private`, created on app startup. **Do not expose `app_private` in Supabase Data API settings.** The authenticated website reads/writes it using the trusted server-side SQL connection, not the public Supabase REST API.

## 4. Render environment variables

Keep all existing variables and add:

```
STAGING_ENABLE_ACCOUNTS=true
APP_PUBLIC_URL=https://cairns-backpacker-jobs.onrender.com
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_YOUR_VALUE
```

Continue to set:

```
APP_MODE=staging
STAGING_ENABLE_FORMS=true
ENABLE_REAL_SEND=false
ENABLE_LOCAL_ADMIN=false
APP_SESSION_SECRET=<your existing stable 32+ character value>
```

`STAGING_USERNAME`, `STAGING_PASSWORD`, and `DATABASE_URL` stay unchanged. **Do not rotate `APP_SESSION_SECRET` unnecessarily**; existing sessions would become invalid. Do not share credentials in chat, source files, or GitHub.

After saving, **Save, rebuild and deploy**. Watch the Render logs. The app creates `app_private.applicant_accounts`, `app_private.web_sessions`, `app_private.application_drafts`, and `app_private.erasure_requests`.

## 5. Test

1. Open `https://<your-service>.onrender.com` and pass the staging password.
2. Click **Mi cuenta (beta privada)**.
3. Enter your own pre-authorised email, request one magic link, and open it **in the same browser**. The code verifies the Supabase Auth access token server-side and stores only a random session identifier in an HttpOnly cookie.
4. Fill your name and phone, check the required privacy acknowledgement, and deliberately leave marketing/feedback unchecked. Click **Guardar perfil**.
5. In Supabase SQL Editor, privately check `SELECT id, email, full_name, phone, marketing_opt_in, feedback_opt_in FROM app_private.applicant_accounts;` (do not publish the results).
6. Create a draft choosing 1–10 businesses. Save an English subject and cover letter. Confirm its personalised previews appear.
7. Sign out, reopen the saved draft URL and confirm you are redirected to login. Sign in again, confirm the draft still exists.
8. Test deleting a draft. If you need to test the erasure request, use only an expendable test account, because it will revoke the account's active sessions and block new sign-ins until manually resolved.
9. Confirm `/connect/google`, `/connect/microsoft`, `/campaigns`, and `/admin/businesses` are still unavailable on hosted staging, and real sends remain disabled.

## 6. What is deliberately NOT done yet

- No CVs are persisted; the original Milestone 9 dummy-file preview remains separate.
- No real job emails or marketing emails are sent.
- No account registration for the public, because the free Supabase mail service is insufficient.
- No durable sending queue on hosted staging.
- Erasure requests are recorded; profile and Supabase Auth identity deletion are **manual operator tasks**. An erasure request clears the person's drafts, profile name/phone and active sessions, and disables communication permissions immediately, but retains their email for the operator to finish deleting the Supabase Auth identity. This is not a claim of completed erasure.
- No recovery guarantees or backup policy for the Supabase Free plan. Establish these before serving applicants.
- The privacy disclosure in the beta is provisional; replace it with a full policy naming the data controller, legal basis, recipients, processors, retention and contact methods before inviting external users.

## 7. Rollback

On Render set `STAGING_ENABLE_ACCOUNTS=false`, **Save, rebuild and deploy**. The hosted account routes disappear. This does **not** erase the new private PostgreSQL tables; handle retained records carefully.

## 8. GitHub

Run `git status` and verify none of the following are staged: `.env`, `.env.staging`, credentials, private databases or CVs. Then:

```
git add .
git commit -m "Milestone 10: private account beta and saved drafts"
git push
```

After this milestone, **Milestone 11** should address secure private CV storage with automatic expiry, a durable worker queue, and provider-compliant sending controls, before public application delivery.
