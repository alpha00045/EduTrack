-- Phase 2: tenant-isolated organization student data.
-- Apply manually after migrations/003_organization_registration.sql.
-- Legacy single-admin students table is intentionally not modified.
CREATE TABLE IF NOT EXISTS organization_students (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    roll_number VARCHAR(40) NOT NULL,
    name VARCHAR(100) NOT NULL,
    math NUMERIC(5,2) NOT NULL CHECK (math BETWEEN 0 AND 100),
    science NUMERIC(5,2) NOT NULL CHECK (science BETWEEN 0 AND 100),
    english NUMERIC(5,2) NOT NULL CHECK (english BETWEEN 0 AND 100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (organization_id, roll_number),
    UNIQUE (organization_id, id)
);
CREATE INDEX IF NOT EXISTS idx_org_students_org_name
    ON organization_students (organization_id, LOWER(name));

CREATE TABLE IF NOT EXISTS organization_student_profiles (
    organization_id BIGINT NOT NULL,
    student_id BIGINT NOT NULL,
    date_of_birth DATE,
    gender VARCHAR(40),
    email VARCHAR(254),
    phone VARCHAR(30),
    guardian_name VARCHAR(120),
    guardian_phone VARCHAR(30),
    address VARCHAR(500),
    admission_number VARCHAR(80),
    joining_date DATE,
    admission_standard VARCHAR(40),
    photo_data BYTEA,
    photo_mime VARCHAR(30),
    notes VARCHAR(2000),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (organization_id, student_id),
    FOREIGN KEY (organization_id, student_id)
      REFERENCES organization_students (organization_id, id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS organization_student_assessments (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    student_id BIGINT NOT NULL,
    academic_year VARCHAR(20) NOT NULL,
    standard VARCHAR(40) NOT NULL,
    term VARCHAR(40) NOT NULL,
    subject VARCHAR(60) NOT NULL,
    marks_obtained NUMERIC(7,2) NOT NULL CHECK (marks_obtained >= 0),
    maximum_marks NUMERIC(7,2) NOT NULL CHECK (maximum_marks > 0),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (organization_id, student_id)
      REFERENCES organization_students (organization_id, id) ON DELETE CASCADE,
    CHECK (marks_obtained <= maximum_marks)
);
CREATE INDEX IF NOT EXISTS idx_org_assessments_student_year
    ON organization_student_assessments (organization_id, student_id, academic_year);

CREATE TABLE IF NOT EXISTS organization_attendance (
    organization_id BIGINT NOT NULL,
    student_id BIGINT NOT NULL,
    attendance_date DATE NOT NULL,
    status VARCHAR(10) NOT NULL CHECK (status IN ('present','absent','late')),
    marked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (organization_id, student_id, attendance_date),
    FOREIGN KEY (organization_id, student_id)
      REFERENCES organization_students (organization_id, id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_org_attendance_org_date
    ON organization_attendance (organization_id, attendance_date);
