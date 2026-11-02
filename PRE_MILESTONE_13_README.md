# Cairns Backpacker Jobs — Pre-Milestone 13 update

**Purpose:** Refresh the Spanish-language UI, add prominent creator links, improve selection, and prepare the **local-only** employer campaign engine for realistic business directories. This is an incremental patch on top of **Milestone 12**, not a new standalone project.

## What changes

1. New teal/ink/cream responsive visual system: DM Sans + Outfit (Google Fonts with system fallbacks), consistent cards, forms, navigation and footer across existing pages. The line immediately under each page title reads: **Hecho por Juan en Cairns · Seguime en Instagram ↗ · Mandame tu feedback ✉**. These links use the Instagram and email address you supplied.
2. Business directory adds **Seleccionar todos los visibles** and **Quitar selección**. The first acts on eligible checkboxes *currently shown by filters/search*, and never checks disabled businesses. The saved-draft form also adds Select All/Clear buttons.
3. The hard-coded **20 attempts / 24 hours** app-local cap is removed. That does **not** remove Gmail/Outlook sending limits, throttling, mailbox anti-spam rules or the user's responsibility to send relevant, permitted messages.
4. The delay between local real send attempts changes from **8 to 2 seconds**. Provider `429` errors still stop the queue, and ambiguous/uncertain results aren't automatically retried. Two seconds is a test default, not an officially permitted sending rate.
5. Duplicate prevention changes from **30 to 7 days**. Recently accepted/uncertain businesses are **skipped**, not blockers for applying to all *other* businesses.
6. One business can now have a **primary** email and up to **five additional** emails, manually reviewed and approved by the local administrator. The actual employer send is **one message with multiple To recipients**, **not separate individual messages**, and recipients can see the other recipients in that message. Any normal reception or general contact inbox may be eligible if confirmed suitable for job applications. This does **not** waive the need to check that the address is current and appropriate for these enquiries.
7. Maximum business **selection size** is increased from 10 to 500 in both staging and local flows. This is a technical per-selection guard, **not** a 24-hour email quota. Most Cairns directories will be far smaller.
8. Add `/privacidad` to the previously missing staging routes, and ensure `app_private` access architecture is unchanged.

## Before installing

- Make a Git commit of your current, working Milestone 12. Back up your business database before changing backend models.
- If you independently modified `app/main.py`, `app/routes/account_beta.py` or the admin forms since the last milestone, **compare and merge instead of blindly overwriting**.
- Keep `app/services/account_auth.py` (your magic-link redirect fix). **This patch doesn't include or replace it.**
- Keep `.env` and all secrets out of Git.

## Installation from ZIP

1. Extract this ZIP; copy its contents into the **root** of your existing Cairns Backpacker Jobs project, merging `app/` subfolders.
2. VS Code → Terminal (PowerShell), run:

   ```powershell
   git status
   python -m compileall -q app
   ```

3. Review changed files and never upload `.env`, API keys, SQLite files or CVs.
4. Run the website locally if you like and test selection; if using your previously configured Supabase-backed Render staging, deploy by running:

   ```powershell
   git add app PRE_MILESTONE_13_README.md
   git commit -m "Improve website design and business selection"
   git push
   ```

5. Render will deploy automatically if enabled. No new Render environment variables are required. **Keep**:

   ```dotenv
   APP_MODE=staging
   ENABLE_REAL_SEND=false
   STAGING_ENABLE_ACCOUNTS=true
   STAGING_ENABLE_FORMS=true
   STAGING_ENABLE_DRAFT_FILES=true
   STAGING_ENABLE_SELF_TEST=true
   ```

6. On startup, `Base.metadata.create_all` creates the new `public.business_extra_emails` table, and the app enables **row-level security with no anonymous/client policies** so the new contact addresses are not exposed via the Supabase REST API. As in earlier milestones, the trusted database owner accesses them directly. Do not add `SELECT` policies for `anon` or `authenticated` without a separate security review.

## Multiple email addresses — use local administrator

The administrator remains deliberately inaccessible on Render; don't enable it there. To edit businesses use the existing local-admin workflow at `http://localhost:8000/admin/businesses` with `APP_MODE=local` and `ENABLE_LOCAL_ADMIN=true`, after configuring your existing admin username/password.

1. Open a business. Keep its main address in **Email para postulaciones**.
2. Put additional addresses in **Emails adicionales** (one per line, up to five). Example: `reception@hotel.example` + `manager@hotel.example` (examples only; do not actually send to `*.example`).
3. Document the business's source and why these are valid channels for **job enquiries**. General reception addresses are fine if relevant; HR-specific addresses are **not** required.
4. Save (this deliberately clears previous contact approvals), then approve the set of addresses using the existing review controls.
5. When local employer sending is eventually enabled after Milestone 13's safety review, the preview shows all approved recipients, and one email addresses all of them. **All recipients are visible in To.**

**Note:** editing local SQLite does not edit Supabase PostgreSQL. If the admin is connected to a different database, those addresses won't appear in the hosted directory. The patch does not add a public admin tool or a database sync feature. For now, the hosted version remains a private no-employer-send preview.

## Test plan

- Refresh hosted staging, ensure the page title has the Instagram and email feedback links, and check `/privacidad`.
- Use filters and search; select all visible eligible businesses, clear selection, select a smaller set, continue to demo.
- Sign in, use **Mi cuenta → Crear un borrador**, select all, save it, open the draft, and simulate a queue with a dummy CV. No employer emails should be sent.
- Local admin: configure two test addresses for one business, review/approve, and verify the preview lists both. Keep `ENABLE_REAL_SEND=false` for these tests.
- In future local real tests, verify the 2-second delay, 7-day deduplication, provider refusal handling and that the user explicitly confirms the addresses.

## Why not completely unlimited actual sends?

Unlimited application-side attempts does not grant unlimited sending permission from an email account. Google's ordinary Gmail service may stop accounts when sending limits are exceeded; personal Gmail's help page describes a 500-per-day threshold. Google Workspace and Microsoft have other rate limits and policies. The project should not automate retries around blocking errors or use multiple accounts to circumvent provider restrictions.

- Gmail consumer limits: https://support.google.com/mail/answer/22839
- Gmail API quotas: https://developers.google.com/workspace/gmail/api/reference/quota
- Microsoft Graph throttling: https://learn.microsoft.com/en-us/graph/throttling

## Rollback

If deployment fails, revert the new commit on GitHub (e.g., `git revert <commit-sha>` followed by `git push`). The new extra-email table is additive, and it doesn't delete the existing `businesses.email` column or business rows. Don't drop tables that contain data simply to roll back the interface.

## Remaining work for Milestone 13

The local employer queue is **not** yet a safe hosted production sender. Priorities: durable OAuth token/session handling; review of employment solicitation/recipient permission and opt-outs; stable worker processing on a suitable host; provider-aware pacing and retry-backoff for confirmed non-sends (not uncertain sends); final privacy/abuse review. `ENABLE_REAL_SEND` **remains `false` on Render**.
