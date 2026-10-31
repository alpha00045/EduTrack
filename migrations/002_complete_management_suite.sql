-- EduTrack feature suite schema.
-- Review and apply manually to the configured PostgreSQL database.
-- The application never runs schema changes automatically.

CREATE TABLE IF NOT EXISTS attendance (
    student_roll INTEGER NOT NULL REFERENCES students (roll_number) ON DELETE CASCADE,
    attendance_date DATE NOT NULL,
    status VARCHAR(10) NOT NULL CHECK (status IN ('present', 'absent', 'late')),
    marked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (student_roll, attendance_date)
);
CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance (attendance_date);
CREATE INDEX IF NOT EXISTS idx_attendance_status_date ON attendance (status, attendance_date);

CREATE TABLE IF NOT EXISTS student_profiles (
    student_roll INTEGER PRIMARY KEY REFERENCES students (roll_number) ON DELETE CASCADE,
    email VARCHAR(254),
    phone VARCHAR(30),
    guardian_name VARCHAR(100),
    date_of_birth DATE,
    address VARCHAR(500),
    notes VARCHAR(2000),
    photo_data BYTEA,
    photo_mime VARCHAR(30),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS student_assessments (
    id BIGSERIAL PRIMARY KEY,
    student_roll INTEGER NOT NULL REFERENCES students (roll_number) ON DELETE CASCADE,
    academic_year VARCHAR(20) NOT NULL,
    term VARCHAR(40) NOT NULL,
    subject VARCHAR(50) NOT NULL,
    marks NUMERIC(5,2) NOT NULL CHECK (marks >= 0 AND marks <= 100),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (student_roll, academic_year, term, subject)
);
CREATE INDEX IF NOT EXISTS idx_assessments_student_year
    ON student_assessments (student_roll, academic_year);

CREATE TABLE IF NOT EXISTS app_settings (
    setting_key VARCHAR(80) PRIMARY KEY,
    setting_value VARCHAR(500) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO app_settings (setting_key, setting_value)
VALUES ('school_name', 'EduTrack'), ('pass_mark', '33')
ON CONFLICT (setting_key) DO NOTHING;
