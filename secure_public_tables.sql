-- Milestone 10: defense in depth for the existing public-schema tables.
-- Run in Supabase SQL Editor before collecting any real applicant data.
-- RLS without user policies denies access through exposed anon/authenticated Data API roles.
-- The FastAPI SQLAlchemy connection uses a PostgreSQL owner role and is unaffected.
DO $$
BEGIN
  IF to_regclass('public.applicant_contacts') IS NOT NULL THEN
    ALTER TABLE public.applicant_contacts ENABLE ROW LEVEL SECURITY;
  END IF;
  IF to_regclass('public.campaigns') IS NOT NULL THEN
    ALTER TABLE public.campaigns ENABLE ROW LEVEL SECURITY;
  END IF;
  IF to_regclass('public.campaign_attempts') IS NOT NULL THEN
    ALTER TABLE public.campaign_attempts ENABLE ROW LEVEL SECURITY;
  END IF;
END $$;
-- app_private is a separate schema and must NOT be added to Data API exposed schemas.
-- Add an appropriate backup strategy before a real public launch.
