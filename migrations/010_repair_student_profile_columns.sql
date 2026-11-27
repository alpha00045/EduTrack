-- EduTrack schema repair: ensure the expanded student profile columns exist.
-- Safe to run more than once; additive only and preserves existing student data.
-- This repairs production databases where migration 008 was only partially applied.

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
    ADD COLUMN IF NOT EXISTS student_status VARCHAR(20);

UPDATE organization_student_profiles
SET student_status = 'Active'
WHERE student_status IS NULL OR BTRIM(student_status) = '';

ALTER TABLE organization_student_profiles
    ALTER COLUMN student_status SET DEFAULT 'Active',
    ALTER COLUMN student_status SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'organization_student_profiles_status_check'
          AND conrelid = 'organization_student_profiles'::regclass
    ) THEN
        ALTER TABLE organization_student_profiles
            ADD CONSTRAINT organization_student_profiles_status_check
            CHECK (student_status IN ('Active', 'Transferred', 'Graduated', 'Inactive'));
    END IF;
END $$;
