-- EduTrack Phase 5: organization exam creation, subject setup, marks entry and publication.
-- Apply after migration 008_student_information_system.sql.
CREATE TABLE IF NOT EXISTS organization_exams (
 id BIGSERIAL PRIMARY KEY, organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 title VARCHAR(160) NOT NULL, academic_year VARCHAR(20) NOT NULL, class_or_course VARCHAR(120),
 term VARCHAR(80), exam_date DATE, published BOOLEAN NOT NULL DEFAULT FALSE, published_at TIMESTAMPTZ,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE (organization_id,id)
);
CREATE INDEX IF NOT EXISTS idx_organization_exams_tenant_date ON organization_exams (organization_id,exam_date DESC,created_at DESC);
CREATE TABLE IF NOT EXISTS organization_exam_subjects (
 id BIGSERIAL PRIMARY KEY, organization_id BIGINT NOT NULL, exam_id BIGINT NOT NULL,
 subject_name VARCHAR(100) NOT NULL, maximum_marks NUMERIC(7,2) NOT NULL CHECK(maximum_marks>0),
 pass_marks NUMERIC(7,2) NOT NULL CHECK(pass_marks>=0 AND pass_marks<=maximum_marks),
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(organization_id,exam_id,id), UNIQUE(organization_id,exam_id,subject_name),
 FOREIGN KEY(organization_id,exam_id) REFERENCES organization_exams(organization_id,id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS organization_exam_results (
 id BIGSERIAL PRIMARY KEY, organization_id BIGINT NOT NULL, exam_id BIGINT NOT NULL,
 student_id BIGINT NOT NULL, exam_subject_id BIGINT NOT NULL,
 marks_obtained NUMERIC(7,2) NOT NULL CHECK(marks_obtained>=0),
 recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(organization_id,exam_id,student_id,exam_subject_id),
 FOREIGN KEY(organization_id,exam_id) REFERENCES organization_exams(organization_id,id) ON DELETE CASCADE,
 FOREIGN KEY(organization_id,student_id) REFERENCES organization_students(organization_id,id) ON DELETE CASCADE,
 FOREIGN KEY(organization_id,exam_id,exam_subject_id) REFERENCES organization_exam_subjects(organization_id,exam_id,id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_organization_exam_results_student ON organization_exam_results(organization_id,student_id,exam_id);
