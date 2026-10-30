# Cairns Backpacker Jobs — Milestone 5 (LOCAL DEVELOPMENT ONLY)

**Integrates with the existing project from Milestones 1–4.** This patch is NOT a standalone project. It expects existing `app/database.py`, `app/models.py`, `app/services/contacts.py`, `app/services/email_builder.py`, `app/routes/businesses.py`, `app/templates/compose.html`, `app/templates/CSS and database. The patch includes an updated `privacy.html` reflecting temporary CV retention; it is a draft and requires your real privacy contact details before launch.

## What it does

- Keeps the CV in RAM for at most 20 minutes, maximum 20 open drafts per process, max 5 MB each; drafts and tokens disappear if the Python process restarts.
- Stores OAuth access tokens only in server RAM and **never in the browser cookie**, SQLite, or files.
- Connects Google or Microsoft via OAuth authorization-code flow with state protection; confirms that the connected email matches the entered address before saving contact/marketing permissions.
- Sends **one test email ONLY TO THE OAUTH-CONNECTED USER'S OWN INBOX**, with CV attachment. It DOES NOT send to employer/business addresses.
- Clears CV and token from memory after a confirmed API submission.

## Install

1. Back up or commit existing work, then overlay files from the zip onto the project root, preserving existing files that aren't in the patch.
2. From VS Code PowerShell, activate venv: `.\\venv\\Scripts\\Activate.ps1` (or `.venv`).
3. Install: `python -m pip install authlib httpx python-dotenv itsdangerous`.
4. Update: `python -m pip freeze > requirements.txt`.
5. Add to your existing `.env` (and check `.gitignore` ignores `.env`): `APP_SESSION_SECRET=...` and the OAuth credentials (see below). Generate secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
6. In `app/templates/compose.html`, inside `<form action="/compose/review" ...>` add:
   `<input type="hidden" name="csrf_token" value="{{ csrf_token }}">`
7. Use `http://localhost:8000` for all browser visits. Do not switch between `localhost` and `127.0.0.1`, because they have distinct cookies/OAuth redirect origins.
8. Start: `python -m uvicorn app.main:app --reload --host localhost`.

## Create OAuth credentials — Google

- Visit https://console.cloud.google.com/ . Create/select a Google Cloud project.
- Enable **Gmail API** under APIs & Services.
- Google Auth Platform: configure consent/branding, choose External (when applicable), add your own Gmail address as test user.
- Add scope `https://www.googleapis.com/auth/gmail.send` and OIDC scopes `openid email`.
- Create an OAuth client of type **Web application**; registered redirect URI **exactly** `http://localhost:8000/auth/google/callback`.
- Copy Client ID and Client secret to `.env` under GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.
- Test only with an account allowed by Google's test-user settings. Public release may require Google OAuth verification (gmail.send is a sensitive scope).

## Create OAuth credentials — Microsoft

- Visit https://entra.microsoft.com/ > Identity > Applications > App registrations > New registration.
- Supported accounts: **Personal Microsoft accounts**, if available, or **Accounts in any organizational directory and personal Microsoft accounts**. The current code deliberately uses the `/consumers` endpoint for **Outlook.com / Hotmail / Live personal accounts only**; organisational accounts are deferred.
- Register redirect URI of platform **Web**: `http://localhost:8000/auth/microsoft/callback`.
- Add delegated Microsoft Graph API permissions `Mail.Send` and `User.Read`.
- Certificates & secrets > New client secret; copy the **secret value**, not secret ID, to `.env` as MICROSOFT_CLIENT_SECRET.
- Copy the Application (client) ID to MICROSOFT_CLIENT_ID.
- Admin consent may be needed for work accounts (depending on their organisation).

## Test

1. Open http://localhost:8000/ and select a test business.
2. `/compose` requires the CSRF hidden field above. Fill the form with the **same email as the Gmail/Outlook account** to be connected, choose a dummy CV, and check the privacy acknowledgement.
3. Click Review. The CV and preview should remain available; check the navigation.
4. Click Connect Gmail (or Outlook), sign in and consent. After returning, the app displays the connected account address (Microsoft OAuth here is for *personal* Outlook/Hotmail/Live accounts).
5. Click **Enviar una prueba a mi propio email**. It sends **one** test message addressed only to the connected user's own account with the CV attached. It never emails any employer.
6. After a successful API response, reload `/compose/ready`: the draft should be gone. If you restart Uvicorn before completing, draft and token are lost and the form must be resubmitted.
7. Check your local `applicant_contacts` table; the verified account's name, email, phone, and optional consent choices should be present. If you connected a different email than the form entry, consent should not be saved.

## Limitations (IMPORTANT)

- Local testing only, **not production ready**: in-memory state works only with one Uvicorn worker/process; `--reload` destroys in-flight drafts and OAuth tokens. Real deployment will need an encrypted/shared short-lived draft store, secure server-side token storage, HTTPS-only cookies, better upload validation/malware scanning, CSRF/rate limits, audits, consent history, and compliance review.
- Starlette may spool incoming uploads temporarily to OS temp storage while parsing a multipart request; the `UploadFile` is closed after validation. The application itself keeps the validated CV in RAM, not on disk.
- After an OAuth connection, contact details are saved; unverified form emails are not persisted by this patch (a safety improvement from the previous milestone).
- Microsoft Graph JSON attachment path is limited to about 2.5 MB for this test; smaller CVs work. For 2.5–5 MB on Outlook, implement Graph upload sessions in a later milestone.
- OAuth app testing and external access limits vary; neither provider integration avoids the need for approvals before a public launch.
- One test only; no queue, retries, delivery confirmations or employer sends. API acceptance isn't a delivery guarantee.
- Review/privacy terms should accurately describe short-lived in-memory CV and marketing consent verification before using real users.
