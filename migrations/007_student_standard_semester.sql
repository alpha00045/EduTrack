-- Add class/standard and semester metadata for filtering student records.
-- Apply this migration before deploying the application changes.
ALTER TABLE students
    ADD COLUMN IF NOT EXISTS standard VARCHAR(40),
    ADD COLUMN IF NOT EXISTS semester VARCHAR(20);

ALTER TABLE organization_student_profiles
    ADD COLUMN IF NOT EXISTS semester VARCHAR(20);

CREATE INDEX IF NOT EXISTS idx_students_standard_semester
    ON students (standard, semester);

CREATE INDEX IF NOT EXISTS idx_org_student_profiles_standard_semester
    ON organization_student_profiles (organization_id, admission_standard, semester);
