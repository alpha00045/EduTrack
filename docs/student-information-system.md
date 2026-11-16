# EduTrack Student Information System

## Scope in this change

- Three entry points are available from `/portal`: Admin, School/Institute, and Student.
- New organization registrations are limited to **School** or **Institute**. Existing legacy organization categories are normalized to Institute by migration 008.
- Student admission captures personal, guardian, emergency, academic, photo, and document details.
- School admissions use class/standard and section. Institute admissions use course and semester.
- Each admission creates an organization-scoped student account with a generated username and a temporary password shown once to the organization admin. The password is hashed in the database and must be changed on first login.
- Student accounts can view their own exam-history records and published notices from their own organization. They cannot access organization-admin routes.
- Organization notices are private to the owning organization.

## Database rollout

1. Take and verify a PostgreSQL backup.
2. Confirm migrations 003 through 007 have already been applied.
3. Review and apply `migrations/008_student_information_system.sql` to the production PostgreSQL database.
4. Deploy the application code after the migration succeeds.
5. Test with a dummy School and a dummy Institute before admitting real students.

Migration 008 does not delete existing student profiles, current marks, or assessment-history rows. It adds enrolment history, student accounts, notices, and document storage. Existing non-School organization types are mapped to Institute to match the new two-type registration flow.

## Important operational notes

- No email, SMS, or OTP delivery is implemented in this phase.
- The temporary password is displayed once after admission. The organization admin must hand it to the student securely.
- The app stores uploaded profile photos and documents in PostgreSQL. Documents are limited to PDF/JPG/PNG/WebP and 5 MB each; profile photos retain the existing 2 MB validation.
- Exam results remain in `organization_student_assessments`; do not overwrite old assessment rows when recording a new exam.
- Do not merge or deploy before the migration and application changes have been reviewed and tested.
