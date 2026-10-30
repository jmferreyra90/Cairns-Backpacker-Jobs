# Milestone 6 — Cola de postulaciones y progreso (DEVELOPMENT ONLY)

**Patch to overlay on your existing Milestone 5 project.** Not a standalone program. Do **not** delete your database or your earlier code. Back up/commit your work before copying files. The patch intentionally includes only changed/new files.

## What you get

- Real-time Spanish progress page with updates every 2 seconds, a list of recipient statuses, and totals. Also a session-only history page at `/mis-postulaciones`. Also allows cancelling future unsent attempts (an in-flight request cannot be undone).
- Default simulation mode: it creates campaign/attempt records, advances one business at a time, **never calls Gmail or Microsoft Graph** and does not send any email.
- Optional real mode gated by `ENABLE_REAL_SEND=true` AND an OAuth connection matching the submitted email AND explicit user checkbox. **Do not enable for a public launch.**
- Maximum 10 businesses per campaign, 20 real attempts per connected sender in a rolling 24h period, 8 seconds between real attempts, and 30-day same-sender/same-business duplicate protection for accepted/uncertain/in-flight sends. These are project safeguards, **not** vendor-guaranteed limits.
- For real sending, the business email must be `email_verified=True` and verified within 90 days. Example/test recipient domains are prohibited in real mode. The user needs to have a legitimate job application purpose and review the recipients.
- The result is `accepted` (provider accepted request) rather than `delivered`. Gmail and Microsoft don't guarantee inbox delivery based on an API success.
- Failed, uncertain, and interrupted attempts are **never retried automatically** to prevent accidental duplicates. On startup, stale running campaigns are marked `interrupted`; `sending` entries become `uncertain`.
- Only a session with the original signed browser cookie can see that campaign's progress; the CV and OAuth token remain RAM-only (M5 behaviour). Campaign records with sender email/businesses/states persist in SQLite.

## Files

Replace the following with the patch version (back up your customisations first):

- `app/main.py`
- `app/routes/applications.py`
- `app/services/mail_api.py`
- `app/services/session_store.py`
- `app/templates/review.html`
- `app/templates/privacy.html`
- `.env.example` (optional; your real `.env` must **not** be overwritten)

Add the following new files in their corresponding folders:

- `app/models_campaign.py`
- `app/routes/campaigns.py`
- `app/services/campaign_queue.py`
- `app/templates/campaign_progress.html`
- `app/templates/campaign_history.html`
- `MILESTONE_6_README.md`

**Keep unchanged** `app/models.py`, `app/database.py`, `app/routes/mail_auth.py`, `app/routes/businesses.py`, `app/services/contacts.py`, `app/services/email_builder.py`, `app/templates/compose.html`, `data/cairns_jobs.db`, your `.env`, and `requirements.txt`.

## Install and run

1. VS Code > Terminal > PowerShell (project root).
2. Activate venv: `.\venv\Scripts\Activate.ps1` (or `.venv` if yours is named that).
3. Confirm `.env` contains OAuth credentials and `APP_SESSION_SECRET` from M5; add `ENABLE_REAL_SEND=false` (recommended).
4. Ensure `authlib`, `httpx`, `python-dotenv`, `itsdangerous`, `email-validator`, `python-multipart`, `SQLAlchemy`, `FastAPI`, `Jinja2`, `uvicorn` are present; if your Milestone 5 installation works, **no new packages** are needed.
5. Start: `python -m uvicorn app.main:app --reload --host localhost`.
6. Visit `http://localhost:8000` (always use `localhost`, not 127.0.0.1, to preserve OAuth cookies).

`Base.metadata.create_all()` creates the two new tables: `campaigns` and `campaign_attempts`. Your existing business/applicant tables are preserved. **Do not re-run the CSV importer**, which may duplicate rows.

## Simulate a campaign (recommended first)

1. On the homepage, select 1–3 *test* businesses with contact emails (maximum 10).
2. Click **Continuar**, fill the form and upload a dummy CV.
3. Review personalised emails, then click **Simular esta campaña (no envía emails)**. OAuth is **not** needed for simulation.
4. The browser redirects to `/campaigns/<id>`. You can stop future attempts with **Detener los próximos envíos**. Watch each status change (`En espera` -> `Procesando` -> `Simulado`). You can refresh the page.
5. The records remain in local SQLite. The CV and OAuth token are cleared after the queue finishes. Running a new campaign requires a new form submission.

## Real sending — advanced local test ONLY

Only after testing simulation and the M5 **single-message-to-yourself** flow, verify a legitimate job-application recipient that agreed to receive applications, set `email_verified=True` and `last_verified` in your business database, and ensure the address isn't a reserved test domain.

- Set `ENABLE_REAL_SEND=true` in `.env`, restart Uvicorn.
- Re-create a draft and connect the same Gmail or personal Outlook account using OAuth.
- Verify each recipient in the previews and tick the explicit confirmation checkbox.
- Click **Enviar postulaciones reales**. This sends real external mail; clicking it should be intentional.
- **For local development, use only addresses whose owners agreed to your test.** Do not enable the feature publicly before privacy, safety and compliance review.

M5 Outlook JSON attachment path remains limited to about 2.5 MB. M6 doesn't implement refresh tokens or durable background workers.

## Data, privacy and limitations

- Simulation creates a `Campaign` with `sender_email` even before OAuth (for a preview/workflow test); it does **not** create an `ApplicantContact` until OAuth verifies email ownership. Use dummy details when testing.
- `CampaignAttempt` stores business names/addresses and status (no CV, no access token).
- Local single process only; `--reload` restarts will interrupt jobs. **Do not run multiple Uvicorn workers.**
- Non-durable RAM draft/token store; each draft lasts at most 20 minutes. A restart destroys these inputs, and the queue is marked interrupted; retry by building a *new* campaign after reviewing statuses. An in-flight request may be uncertain even if a provider accepted it.
- No automated retries, account login for history across devices, unsubscribe workflow, hosted deployment, attachment antivirus, or worker/job infrastructure yet.
- The privacy page is still a **draft**. Provide real operator information, retention/deletion periods, a contact channel and compliance review before collecting genuine user data.
- Gmail and Outlook impose sending quotas/abuse policies. Controlled sending intervals don't guarantee mail is permitted, accepted, or delivered; applications that automate bulk unsolicited messages may be rejected by providers.

## Quick checks

- `http://localhost:8000/docs` should list `POST /campaigns/start`, `GET /campaigns/{campaign_id}`, `GET /campaigns/{campaign_id}/status`, `POST /campaigns/{campaign_id}/cancel`, `GET /mis-postulaciones` as well as M5 routes.
- Verify `.env` ignored: `git check-ignore -v .env` and `git check-ignore -v data/cairns_jobs.db`.
- For a clean checkpoint: `git add . && git commit -m "Add campaign queue and progress tracking"`.
