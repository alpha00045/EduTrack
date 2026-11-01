-- Organization-managed subject catalogue and per-student marks.
-- Existing Math, Science and English columns are retained for backward compatibility.
CREATE TABLE IF NOT EXISTS organization_subjects (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    subject_name VARCHAR(80) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (organization_id, subject_name),
    UNIQUE (organization_id, id)
);

CREATE TABLE IF NOT EXISTS organization_student_subject_marks (
    organization_id BIGINT NOT NULL,
    student_id BIGINT NOT NULL,
    subject_id BIGINT NOT NULL,
    marks NUMERIC(5,2) NOT NULL CHECK (marks BETWEEN 0 AND 100),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (organization_id, student_id, subject_id),
    FOREIGN KEY (organization_id, student_id)
      REFERENCES organization_students (organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, subject_id)
      REFERENCES organization_subjects (organization_id, id) ON DELETE CASCADE
);

-- Seed the existing three subjects for every organization.
INSERT INTO organization_subjects (organization_id, subject_name)
SELECT o.id, s.subject_name
FROM organizations o
CROSS JOIN (VALUES ('Math'), ('Science'), ('English')) AS s(subject_name)
ON CONFLICT (organization_id, subject_name) DO NOTHING;

-- Preserve all existing marks in the new subject-based structure.
INSERT INTO organization_student_subject_marks
    (organization_id, student_id, subject_id, marks)
SELECT st.organization_id, st.id, sub.id, v.marks
FROM organization_students st
CROSS JOIN LATERAL (
    VALUES ('Math', st.math), ('Science', st.science), ('English', st.english)
) AS v(subject_name, marks)
JOIN organization_subjects sub
  ON sub.organization_id = st.organization_id
 AND sub.subject_name = v.subject_name
ON CONFLICT (organization_id, student_id, subject_id)
DO UPDATE SET marks = EXCLUDED.marks, updated_at = CURRENT_TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_org_subjects_org_name
    ON organization_subjects (organization_id, LOWER(subject_name));
CREATE INDEX IF NOT EXISTS idx_org_subject_marks_subject
    ON organization_student_subject_marks (organization_id, subject_id);
