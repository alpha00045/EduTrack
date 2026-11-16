-- EduTrack Phase 4: full student information, academic enrolment, student accounts and notices.
-- Apply manually to the production database only after taking a verified backup.
-- This migration is additive and preserves existing student profiles and assessment history.

-- Normalize legacy organization categories into the two supported portal types.
ALTER TABLE organizations DROP CONSTRAINT IF EXISTS organizations_organization_type_check;
UPDATE organizations
SET organization_type = CASE
    WHEN LOWER(organization_type) = 'school' THEN 'School'
    ELSE 'Institute'
END;
ALTER TABLE organizations
    ADD CONSTRAINT organizations_organization_type_check
    CHECK (organization_type IN ('School', 'Institute'));

-- Expand the existing profile table rather than creating a second student identity table.
ALTER TABLE organization_student_profiles
    ADD COLUMN IF NOT EXISTS father_name VARCHAR(120),
    ADD COLUMN IF NOT EXISTS mother_name VARCHAR(120),
    ADD COLUMN IF NOT EXISTS blood_group VARCHAR(5),
    ADD COLUMN IF NOT EXISTS guardian_email VARCHAR(254),
    ADD COLUMN IF NOT EXISTS emergency_contact_name VARCHAR(120),
    ADD COLUMN IF NOT EXISTS emergency_contact_phone VARCHAR(30),
    ADD COLUMN IF NOT EXISTS section VARCHAR(30),
    ADD COLUMN IF NOT EXISTS academic_year VARCHAR(20),
    ADD COLUMN IF NOT EXISTS previous_institution VARCHAR(180),
    ADD COLUMN IF NOT EXISTS course_name VARCHAR(120),
    ADD COLUMN IF NOT EXISTS student_status VARCHAR(20) NOT NULL DEFAULT 'Active';

ALTER TABLE organization_student_profiles
    ADD CONSTRAINT organization_student_profiles_status_check
    CHECK (student_status IN ('Active', 'Transferred', 'Graduated', 'Inactive'));

-- A student may have multiple enrolments over time; old academic placement is retained.
CREATE TABLE IF NOT EXISTS organization_student_enrolments (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    student_id BIGINT NOT NULL,
    academic_year VARCHAR(20) NOT NULL,
    organization_type VARCHAR(10) NOT NULL CHECK (organization_type IN ('School','Institute')),
    standard VARCHAR(40),
    section VARCHAR(30),
    course_name VARCHAR(120),
    semester VARCHAR(20),
    start_date DATE,
    end_date DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'Active'
        CHECK (status IN ('Active','Completed','Transferred','Withdrawn')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (organization_id, student_id)
        REFERENCES organization_students (organization_id, id) ON DELETE CASCADE,
    UNIQUE (organization_id, student_id, id),
    CHECK (
        (organization_type = 'School' AND standard IS NOT NULL AND course_name IS NULL AND semester IS NULL)
        OR
        (organization_type = 'Institute' AND course_name IS NOT NULL)
    )
);
CREATE INDEX IF NOT EXISTS idx_org_student_enrolments_history
    ON organization_student_enrolments (organization_id, student_id, academic_year DESC);

-- Link the existing organization subject catalogue to a student's current enrolment.
CREATE TABLE IF NOT EXISTS organization_student_enrolled_subjects (
    organization_id BIGINT NOT NULL,
    student_id BIGINT NOT NULL,
    enrolment_id BIGINT NOT NULL,
    subject_id BIGINT NOT NULL,
    PRIMARY KEY (organization_id, student_id, enrolment_id, subject_id),
    FOREIGN KEY (organization_id, student_id)
        REFERENCES organization_students (organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, student_id, enrolment_id)
        REFERENCES organization_student_enrolments (organization_id, student_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, subject_id)
        REFERENCES organization_subjects (organization_id, id) ON DELETE CASCADE
);

-- Student portal identity. No email/SMS delivery is performed by this schema.
-- The application must generate a one-time temporary password, show it once to the
-- organization admin, store only its hash, and require a password change at first login.
CREATE TABLE IF NOT EXISTS organization_student_accounts (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    student_id BIGINT NOT NULL,
    username VARCHAR(80) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    must_change_password BOOLEAN NOT NULL DEFAULT TRUE,
    account_status VARCHAR(20) NOT NULL DEFAULT 'Active'
        CHECK (account_status IN ('Active','Disabled','Locked')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (organization_id, student_id),
    FOREIGN KEY (organization_id, student_id)
        REFERENCES organization_students (organization_id, id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_org_student_accounts_tenant
    ON organization_student_accounts (organization_id, username);

-- Organization-owned notices. Student portal queries must always scope by organization_id.
CREATE TABLE IF NOT EXISTS organization_notices (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    title VARCHAR(180) NOT NULL,
    body TEXT NOT NULL,
    audience VARCHAR(20) NOT NULL DEFAULT 'Students'
        CHECK (audience IN ('Students','All')),
    published BOOLEAN NOT NULL DEFAULT FALSE,
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_org_notices_published
    ON organization_notices (organization_id, published, published_at DESC);

-- Private student documents remain scoped to the owning organization and student.
CREATE TABLE IF NOT EXISTS organization_student_documents (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    student_id BIGINT NOT NULL,
    document_name VARCHAR(180) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    file_data BYTEA NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (organization_id, student_id)
        REFERENCES organization_students (organization_id, id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_org_student_documents_owner
    ON organization_student_documents (organization_id, student_id);
