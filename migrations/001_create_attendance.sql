-- EduTrack attendance table
-- Review and apply this migration manually to the configured PostgreSQL database.
-- It is intentionally not executed automatically by the web application.

CREATE TABLE IF NOT EXISTS attendance (
    student_roll INTEGER NOT NULL
        REFERENCES students (roll_number) ON DELETE CASCADE,
    attendance_date DATE NOT NULL,
    status VARCHAR(10) NOT NULL
        CHECK (status IN ('present', 'absent', 'late')),
    marked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (student_roll, attendance_date)
);

CREATE INDEX IF NOT EXISTS idx_attendance_date
    ON attendance (attendance_date);

CREATE INDEX IF NOT EXISTS idx_attendance_status_date
    ON attendance (status, attendance_date);
