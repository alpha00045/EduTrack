-- EduTrack organization registration and verification.
-- Apply manually to Supabase after reviewing. No application route runs DDL.
CREATE TABLE IF NOT EXISTS organizations (
    id BIGSERIAL PRIMARY KEY,
    organization_name VARCHAR(150) NOT NULL,
    organization_type VARCHAR(40) NOT NULL
        CHECK (organization_type IN ('School','College','University','Coaching Institute','Other')),
    registration_number VARCHAR(80),
    contact_person VARCHAR(120) NOT NULL,
    email VARCHAR(254) NOT NULL,
    phone VARCHAR(25) NOT NULL,
    address VARCHAR(500) NOT NULL,
    password_hash TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','approved','rejected','suspended')),
    rejection_reason VARCHAR(500),
    reviewed_by VARCHAR(120),
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_organizations_email_lower
    ON organizations (LOWER(email));
CREATE UNIQUE INDEX IF NOT EXISTS uq_organizations_registration_number
    ON organizations (registration_number)
    WHERE registration_number IS NOT NULL AND registration_number <> '';
CREATE INDEX IF NOT EXISTS idx_organizations_status_created
    ON organizations (status, created_at DESC);
