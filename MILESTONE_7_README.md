# Milestone 7 — Cairns business directory and LOCAL admin dashboard

This ZIP is an **overlay** for your existing Milestone 6 project. It is NOT a standalone application. It will not replace `data/cairns_jobs.db`, the user's contacts, or your old campaigns.

## What this patch adds

- Public business directory showing real Cairns entries **even when an application email is not known**. The checkbox is unavailable until a business has an email; unapproved emails are clearly labelled as pending. The Spanish category filters, search and selection counter remain in place.
- Private **LOCAL ONLY** admin editor at `http://localhost:8000/admin/businesses`: add/edit/deactivate businesses, enter manager/contact details, save original source URLs and review notes, approve or block email channels.
- `BusinessContactReview` model in an **additional** `business_contact_reviews` table. No migration is needed for the original `businesses` table.
- Add-only CSV importer, via the admin dashboard or PowerShell. New records start **unverified**; existing businesses are never overwritten. Includes a 14-business starter CSV.
- Milestone 6 real sending checks both existing `Business.email_verified` / `last_verified` and the new explicit `BusinessContactReview.status='approved'` before beginning **and before every send**. Simulations still work with sample businesses.
- No new Python dependencies compared with Milestone 6.

## File instructions — preserve your folders

**Replace** these existing files (commit/backup first):

- `app/main.py`
- `app/constants.py`
- `app/routes/businesses.py`
- `app/services/campaign_queue.py`
- `app/templates/index.html`

**Add** these new files:

- `app/models_directory.py`
- `app/routes/admin_businesses.py`
- `app/services/directory_import.py`
- `app/import_directory.py`
- `app/templates/admin_business_list.html`
- `app/templates/admin_business_form.html`
- `data/cairns_businesses_seed.csv`
- `MILESTONE_7_README.md`

**Keep unchanged** `app/database.py`, `app/models.py`, `app/models_campaign.py`, `app/routes/applications.py`, `app/routes/campaigns.py`, `app/routes/mail_auth.py`, `app/services/contacts.py`, `app/services/email_builder.py`, `app/services/mail_api.py`, `app/services/session_store.py`, `app/templates/compose.html`, `app/templates/review.html`, `app/templates/privacy.html`, `app/static/css/style.css`, `data/cairns_jobs.db`, and your `.env`.

## Configure local-only admin

In `.env`, **retain** your previous settings, especially `APP_SESSION_SECRET`, OAuth credentials, and:

```dotenv
ENABLE_REAL_SEND=false
ENABLE_LOCAL_ADMIN=true
LOCAL_ADMIN_USERNAME=admin
LOCAL_ADMIN_PASSWORD=REPLACE_WITH_LONG_RANDOM_VALUE
```

To generate a password in PowerShell:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy output to `.env`. Do not upload `.env` to GitHub. Do **not** expose this local HTTP Basic admin interface over the internet. It uses a loopback-only check + password, and is for local development; production will need secure authenticated admin accounts, HTTPS, protection from brute-force attempts and a proper audit trail.

## Start and inspect

Open VS Code > Terminal > PowerShell. Activate `.\venv\Scripts\Activate.ps1` (or `.venv`) then:

```powershell
python -m uvicorn app.main:app --reload --host localhost
```

Visit `http://localhost:8000` for the public directory and `http://localhost:8000/admin/businesses` for the admin editor. Your browser will request the local admin username and password.

## Import seed businesses — preview first

The starter CSV was compiled from Cairns public business listings and a few official websites on **30 October 2026**. It contains public business names and locations, not a guarantee of current vacancies. Only one explicitly public People & Culture address was included as a *candidate* recruitment contact, but still begins UNVERIFIED. Most emails are intentionally blank rather than guessed.

PowerShell, from the project root:

```powershell
python -m app.import_directory data/cairns_businesses_seed.csv
```

This is a **dry run**: it only reports how many would be new.

To add the missing businesses:

```powershell
python -m app.import_directory data/cairns_businesses_seed.csv --apply
```

Or import the CSV through the private admin dashboard. Running it again **skips** already imported businesses based on their case-insensitive name and category; it doesn't overwrite them or re-verify emails.

### CSV columns

`name,category,address,phone,email,website,manager_name,source_url,notes`

Use English values for category, e.g. `Hotel`, `Hostel`, `Restaurant`, `Cafe`, `Bar`, `Pub`.

## How to approve an actual job-application address

1. Visit `/admin/businesses`, click Edit on the business.
2. Look for a *genuine application channel*: careers page, a publicly designated recruitment email, or explicit confirmation by the business that a specific address accepts CVs. Avoid general reservations/customer service addresses unless confirmed for employment enquiries.
3. Enter the contact email, website if useful, the specific `source_url`, and a clear explanation (who confirmed it / where applications are invited). Save the business.
4. Check that the record is active. Then read the approval confirmation and click **Aprobar contacto para postulaciones**. This sets `email_verified=True`, `last_verified=today`, and the review status to `approved`.
5. Any subsequent save **revokes** approval; repeat your review and approve again. Blocking a record or marking it inactive prevents later real sends. Milestone 6's 90-day review freshness check still applies.

**Never use source presence alone as proof that an inbox accepts job applications**. Do not guess manager names or email formats. A current email can be a real address yet be unsuitable for job applications.

## Verification tests

1. Keep `ENABLE_REAL_SEND=false`.
2. Confirm `http://localhost:8000/admin/businesses` prompts for the local password; with `ENABLE_LOCAL_ADMIN=false`, admin is inaccessible.
3. Dry-run then import the seed, check that public directory shows new entries; most are visible but not selectable.
4. Add a fictional test venue with an `example.com` email; it can be used only in *simulations*, never real sending.
5. Edit/deactivate a venue and check it disappears from the public directory; reactivate to restore.
6. Edit a contact email and check that any previous approval is revoked. Check the CSV import does not overwrite edits.
7. Complete a **simulated** campaign and see Milestone 6 progress statuses.
8. Verify in `http://localhost:8000/docs` that admin endpoints are present; do not consider them production-safe merely because they exist.

## Notes on sources

- Crystalbrook Flynn official People & Culture contact: https://www.crystalbrookcollection.com/flynn/more/contact
- Crystalbrook hotel locations: https://www.crystalbrookcollection.com/
- Pullman Cairns International hotel: https://all.accor.com/hotel/8772/index.en.shtml
- YHA Cairns Central: https://www.yha.com.au/hostels/qld/cairns-and-far-north-queensland/cairns-backpackers-hostel/
- Salt House (official employment section): https://salthouse.com.au/contact/
- Other venues and addresses in the seed were sourced from public local listings. Independently verify details and appropriate recruitment channels before marking them approved.

## Known limitations

- Admin uses HTTP Basic authentication only on localhost and is **not** suitable for public deployment.
- CSV import is add-only, not a merging service or automatic email validator.
- No website scraping or auto-harvesting of email addresses; manager names remain blank unless manually confirmed.
- The original Milestone 6 single-process background queue is not a durable production worker; retain `ENABLE_REAL_SEND=false` during development.
- Applicant privacy policy and unsubscribe functionality still need completion before launch.
- Tracking real delivered emails or actual job vacancies is not yet implemented.

Save a checkpoint after testing:

```powershell
git add .
git commit -m "Add Cairns business directory and local admin dashboard"
```
